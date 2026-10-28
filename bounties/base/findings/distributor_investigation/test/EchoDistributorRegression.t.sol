// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.23;

import {Test, console2} from "forge-std/Test.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import {IDistributor} from "./EchoDistributorReplayPoC.t.sol";

contract MockERC20Reg is ERC20 {
    constructor() ERC20("Mock Token", "MCK") {
        _mint(msg.sender, 1_000_000 ether);
    }
}

/// @notice Reference remediation implementation: Consumed Digest Gate for Echo Distributor
contract PatchedDistributorGate {
    IDistributor public immutable distributor;

    mapping(bytes32 => bool) public consumedDigests;

    error SignatureAlreadyConsumed(bytes32 digest);

    bytes32 constant CLAIM_TYPEHASH = keccak256(
        "ClaimData(bytes16 tokenDistributionUUID,bytes16 entityUUID,address receiver,uint256 amount,Price price,uint256 expiresAt)Price(uint256 tokenPriceUSDCNumerator,uint256 tokenPriceUSDCDenominator)"
    );
    bytes32 constant PRICE_TYPEHASH = keccak256("Price(uint256 tokenPriceUSDCNumerator,uint256 tokenPriceUSDCDenominator)");
    bytes32 constant CARRY_WITHDRAWAL_TYPEHASH = keccak256(
        "CarryWithdrawalData(bytes16 tokenDistributionUUID,bytes16 entityUUID,address receiver,uint256 amount,uint256 expiresAt)"
    );

    constructor(address _distributor) {
        distributor = IDistributor(_distributor);
    }

    function computeClaimDigest(IDistributor.ClaimData memory data) public view returns (bytes32) {
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
        return MessageHashUtils.toTypedDataHash(distributor.domainSeparator(), structHash);
    }

    function computeCarryDigest(IDistributor.CarryWithdrawalData memory data) public view returns (bytes32) {
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
        return MessageHashUtils.toTypedDataHash(distributor.domainSeparator(), structHash);
    }

    function claimGuarded(
        IDistributor.ClaimData calldata claimData,
        bytes calldata claimSignatureUser,
        bytes calldata claimSignaturePlatform,
        IDistributor.Claimer calldata user,
        bytes32[] calldata merkleProof,
        bool pullUnlocked
    ) external {
        bytes32 digest = computeClaimDigest(claimData);
        if (consumedDigests[digest]) {
            revert SignatureAlreadyConsumed(digest);
        }
        consumedDigests[digest] = true;

        distributor.claim(claimData, claimSignatureUser, claimSignaturePlatform, user, merkleProof, pullUnlocked);
    }

    function withdrawCarryGuarded(
        IDistributor.CarryWithdrawalData calldata data,
        bytes calldata userSignature,
        bytes calldata platformSignature
    ) external {
        bytes32 digest = computeCarryDigest(data);
        if (consumedDigests[digest]) {
            revert SignatureAlreadyConsumed(digest);
        }
        consumedDigests[digest] = true;

        distributor.withdrawCarry(data, userSignature, platformSignature);
    }
}

contract EchoDistributorRegressionTest is Test {
    address constant DISTRIBUTOR_IMPL = 0x1798D23f29968b4fff7A60A90645B0939d04f47E;

    MockERC20Reg token;
    IDistributor distributor;
    PatchedDistributorGate gate;

    uint256 userPrivateKey = 0xA11CE;
    address userAddress;

    uint256 dealLeadPrivateKey = 0xDEA1;
    address dealLeadAddress;

    uint256 platformSignerPrivateKey = 0xB0B;
    address platformSignerAddress;

    bytes16 constant DISTRIBUTION_UUID = 0x11111111111111111111111111111111;
    bytes16 constant ENTITY_UUID = 0x22222222222222222222222222222222;
    bytes16 constant DEAL_LEAD_UUID = 0x33333333333333333333333333333333;

    IDistributor.Claimer claimer;

    function setUp() public {
        vm.createSelectFork("https://mainnet.base.org");

        userAddress = vm.addr(userPrivateKey);
        dealLeadAddress = vm.addr(dealLeadPrivateKey);
        platformSignerAddress = vm.addr(platformSignerPrivateKey);

        token = new MockERC20Reg();

        claimer = IDistributor.Claimer({
            entityUUID: ENTITY_UUID,
            signer: userAddress,
            amountInvestedUSDC: 1_000 * 1e6,
            distributionShares: 10_000,
            notChargedCarry: false
        });

        IDistributor.Claimer[] memory claimers = new IDistributor.Claimer[](1);
        claimers[0] = claimer;

        IDistributor.CarryWithdrawer[] memory carryWithdrawers = new IDistributor.CarryWithdrawer[](1);
        carryWithdrawers[0] = IDistributor.CarryWithdrawer({
            entityUUID: DEAL_LEAD_UUID,
            signer: dealLeadAddress,
            carryBPS: 2000
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
            platformCarryBPS: 0
        });

        address proxyAdmin = address(0xAD11111);
        TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(DISTRIBUTOR_IMPL, proxyAdmin, hex"");
        distributor = IDistributor(payable(address(proxy)));
        distributor.initialize(init);

        gate = new PatchedDistributorGate(address(distributor));

        // Fund distributor with 1,000 tokens
        token.transfer(address(distributor), 1_000 ether);
    }

    function _signClaim(IDistributor.ClaimData memory data, uint256 privKey) internal view returns (bytes memory) {
        bytes32 digest = gate.computeClaimDigest(data);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function _signCarryWithdrawal(IDistributor.CarryWithdrawalData memory data, uint256 privKey) internal view returns (bytes memory) {
        bytes32 digest = gate.computeCarryDigest(data);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function test_Regression_PatchedGate_BlocksClaimReplay() public {
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

        // 1st execution: Succeeds normally
        gate.claimGuarded(claimData, sigUser, sigPlatform, claimer, proof, false);
        assertEq(token.balanceOf(receiver), 400 ether);

        // 2nd execution (Replay Attempt): Must revert with SignatureAlreadyConsumed
        bytes32 digest = gate.computeClaimDigest(claimData);
        vm.expectRevert(abi.encodeWithSelector(PatchedDistributorGate.SignatureAlreadyConsumed.selector, digest));
        gate.claimGuarded(claimData, sigUser, sigPlatform, claimer, proof, false);

        // Receiver balance remains exactly 400 ether (replay blocked)
        assertEq(token.balanceOf(receiver), 400 ether);
    }

    function test_Regression_PatchedGate_AllowsFreshVoucher() public {
        address receiver = address(0xCAFE);

        IDistributor.ClaimData memory claim1 = IDistributor.ClaimData({
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

        bytes memory sigUser1 = _signClaim(claim1, userPrivateKey);
        bytes memory sigPlatform1 = _signClaim(claim1, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        // 1st claim
        gate.claimGuarded(claim1, sigUser1, sigPlatform1, claimer, proof, false);

        // 2nd claim with a FRESH voucher at $10.00 (honest pricing)
        IDistributor.ClaimData memory claim2 = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: receiver,
            amount: 400 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 10e6, // $10.00 USDC
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser2 = _signClaim(claim2, userPrivateKey);
        bytes memory sigPlatform2 = _signClaim(claim2, platformSignerPrivateKey);

        // Fresh voucher succeeds and charges carry!
        gate.claimGuarded(claim2, sigUser2, sigPlatform2, claimer, proof, false);

        // Carry generated: 68 tokens
        assertEq(distributor.totalCarryGenerated(), 68 ether);
        // Receiver gets 400 + 332 = 732 ether
        assertEq(token.balanceOf(receiver), 732 ether);
    }

    function test_Regression_PatchedGate_BlocksCarryWithdrawalReplay() public {
        // Step 1: Generate carry in pool
        address userReceiver = address(0xCAFE);
        IDistributor.ClaimData memory claimHigh = IDistributor.ClaimData({
            tokenDistributionUUID: DISTRIBUTION_UUID,
            entityUUID: ENTITY_UUID,
            receiver: userReceiver,
            amount: 1_000 ether,
            price: IDistributor.Price({
                tokenPriceUSDCNumerator: 10e6,
                tokenPriceUSDCDenominator: 1e18
            }),
            expiresAt: block.timestamp + 30 days
        });

        bytes memory sigUser = _signClaim(claimHigh, userPrivateKey);
        bytes memory sigPlatform = _signClaim(claimHigh, platformSignerPrivateKey);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(bytes.concat(keccak256(abi.encode(claimer))));

        distributor.claim(claimHigh, sigUser, sigPlatform, claimer, proof, false);
        assertEq(distributor.totalCarryGenerated(), 180 ether);

        // Step 2: Deal lead signs 50-token partial withdrawal
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

        // 1st withdrawal through gate: succeeds
        gate.withdrawCarryGuarded(carryData, leadSig, platSig);
        assertEq(token.balanceOf(dealLeadReceiver), 50 ether);

        // 2nd withdrawal through gate (Replay Attempt): must revert with SignatureAlreadyConsumed
        bytes32 digest = gate.computeCarryDigest(carryData);
        vm.expectRevert(abi.encodeWithSelector(PatchedDistributorGate.SignatureAlreadyConsumed.selector, digest));
        gate.withdrawCarryGuarded(carryData, leadSig, platSig);

        // Deal lead balance remains 50 ether (replay blocked)
        assertEq(token.balanceOf(dealLeadReceiver), 50 ether);
    }
}
