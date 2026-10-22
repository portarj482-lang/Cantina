<!-- SCOPE START -->
# Program Scope: Base (Coinbase Onchain Bug Bounty)
**Cantina Competition ID:** `55316f42-3c5e-4746-9bd0-0f18dcbc344b`
**URL:** https://cantina.xyz/code/55316f42-3c5e-4746-9bd0-0f18dcbc344b/overview?overviewTab=1&assetGroup=1

## Tier 0 Rewards
- Critical: Up to $5,000,000
- High: Up to $500,000
- Medium: Up to $50,000
- Low: Up to $5,000
- Informational: Up to $0

### Tier 0 Products
We have three products in Tier 0: Base, cbBTC, and cbETH.
- **Base:** An L2 that rolls up to Ethereum (L1). Scope: L2 & L1 mainnet addresses.
- **cbBTC:** Wrapped BTC, backed 1:1 by Coinbase. Scope: Contracts on Base, Ethereum, Solana, and Arbitrum — and any other networks we may add in the future.
- **cbETH:** Wrapped staked ETH that represents ETH staked through Coinbase. Scope: Contracts on Ethereum.

## Tier 1 Rewards
- Critical: Up to $500,000
- High: Up to $50,000
- Medium: Up to $5,000
- Low: Up to $500
- Informational: Up to $0

Tier 1 encapsulates everything that is not in Tier 0. In other words, Tier 1 has mainnet contracts associated with all products not in Tier 0 that are deployed by Coinbase. Below, we provide a list of contracts in this tier, which is not meant to be exhaustive.

### Account Policies
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| PolicyManager | Base | Core orchestrator for installing, replacing, and executing policies on smart contract wallets. Acts as an execution-enabled wallet owner and enforces policy lifecycle and validity rules. | 0x75b3015780776952102a8bFA6202d2e3c1F4EFc5 |
| MorphoLendPolicy | Base | Policy for recurring deposits into Morpho vaults under per-period spend limits. Authorizes lend automation within bounds set at install time. | 0x015Cf8dbB7F1045280B96d0afd308dFa7AcB84F0 |
| MorphoLoanProtectionPolicy | Base | One-shot collateral top-up policy for liquidation protection on Morpho borrow positions. Limited to a single active instance per account and market. | 0x001B6f938eA6D0A57D02B3e9503b958149A2a7e3 |
| MorphoWETHLoanProtectionPolicy | Base | WETH-collateral variant of MorphoLoanProtectionPolicy. Same one-shot liquidation-protection semantics for WETH-collateralized markets. | 0xe14A101ADF9AE492Dd8e9D2ED7763460A6AE8Cd7 |
| PublicERC6492Validator | Base | ERC-6492 signature validation for wallet-signed policy installs and replacements. Used by PolicyManager for signed lifecycle flows; no privileged role. | 0xBde308aEFDdF0fc0bd2156348F380719620d65Cc |

### Base AppChains
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| DeployChain | Base | Preinstall deployment factory for creating chains. Manages chain initialization with precompiled contracts. | 0xe8c6D9460Ce61D260260d27f30bde8b8d1a8341e |
| SuperchainConfig | Base | Configuration contract for Superchain deployments. Controls global superchain settings and parameters. | 0xc5b0B126fFD9D36084af85359a07Fb798A405aDc |

### Basenames
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| OpenEdition721Mint | Base | ERC721 NFT minting contract for open edition collections. Enables unlimited minting of digital collectibles. | 0x75D2eA122cC20B6e661775Ac18ffF0B4547B9fe6 |
| EARegistrarController | Base | ENS domain registration controller for Early Access users. Handles discounted domain registrations for qualifying addresses. | 0xd3e6775Ed9B7dC12B205C8E608Dc3767B9e5eFdA |
| L2Resolver | Base | ENS resolver for Base usernames with CCIP-read support. Manages name resolution and record storage for .base.eth domains. | 0xC6d566A56A1aFf6508b41f6c90ff131615583BCD |
| RegistrarController | Base | Main domain registration and renewal controller. Handles pricing, discounts, and domain lifecycle management. | 0x4cCb0BB02FCABA27e82a56646E81d8c5bC4119a5 |
| CB1DiscountValidator | Base | Validates eligibility for CB1 holder discounts. Checks ownership of Coinbase One NFTs for domain registration discounts. | 0x9de4Ab12320684cec803Edb72aA3a920250d392C |
| BaseETHDiscountValidator | Base | Validates ETH-based discount eligibility on Base. Checks ETH balance thresholds for domain registration discounts. | 0x55564490a44FDC2aEEa54B60eB1c79F124FD88b9 |
| CBIdDiscountValidator | Base | Validates Coinbase ID verification for discounts. Checks verified Coinbase account status for domain pricing benefits. | 0x0A484e560946818787135EAD632771589523dE82 |
| VADiscountValidator | Base | Validates early access discount eligibility. Manages whitelist-based domain registration discounts for qualifying users. | 0x012076854d030128dc72B34621287Bb585210315 |
| BNSDiscountValidator | Base | Validates eligibility for Basename NFT holder discounts. Checks ownership of early Basename NFTs for registration benefits. | 0x20b433c640DFb8c2e3C6aBB0533314b2d7B9f2FF |
| OCSNFTDiscountValidator | Base | Validates discounts for OnChain Summer NFT holders. Checks ownership of qualifying OnChain Summer NFTs for domain discounts. | 0x55246A2AE466257B2fB54d4BB881Fb3f17D8e03e |
| EAExponentialPremiumPriceOracle | Base | Early Access pricing oracle with exponential premium decay. Implements launch pricing with time-based premium reduction. | 0x46114792Cc08Baf79006f25Ec9eE23AC64e119ca |
| ExponentialPremiumPriceOracle | Base | Standard pricing oracle with exponential premium decay. Calculates domain prices with time-based premium reduction after expiry. | 0x508CFE43aa84b8048cB6d39037cE0dc96d8aDc75 |
| BaseRegistrar | Base | Core domain registration and ownership management contract. ERC721-based registrar for .base.eth domain ownership and transfers. | 0x03c4738Ee98aE44591e1A4A4F3CaB6641d95DD9a |
| EaMerkleDiscountValidator | Base | Early Access merkle proof discount validator. Validates whitelist eligibility using merkle tree proofs for domain discounts. | 0x6E89d99643DB1223697C77A9F8B2Cb07E898e743 |
| ReverseRegistrar | Base | Manages reverse ENS lookups for addresses. Allows setting primary names for addresses for reverse resolution. | 0x79EA96012eEa67A83431F1701B3dFf7e37F9E282 |
| DevfolioDiscountValidator | Base | Validates discounts for Devfolio platform users. Checks eligibility for developer-focused domain registration discounts. | 0xB635802085b405A9C8BA7225ae866f60b63d8503 |
| LaunchAuctionPriceOracle | Base | Auction-based pricing oracle for launch phase. Implements Dutch auction pricing for premium domain name launches. | 0xd53B558e1F07289acedf028d226974AbBa258312 |
| Registry | Base | Core ENS registry for .base.eth domains. Central registry managing domain ownership and resolver assignments. | 0xB94704422c2a1E396835A571837Aa5AE53285a95 |
| L1Resolver | Ethereum | Layer 1 ENS resolver for cross-chain resolution. Handles ENS resolution queries on Ethereum for Base domains. | 0xde9049636F4a1dfE0a64d1bFe3155C0A14C54F31 |
| L1Resolver | Ethereum | Layer 1 ENS resolver for cross-chain resolution. Handles ENS resolution queries on Ethereum for Base domains. | 0x480F8F2FfE823Dc70F499Cc2542C42a3a6aD3f20 |

### Coinbase Attestations
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| EAS | Base | Ethereum Attestation Service for creating on-chain attestations. Enables verifiable claims and credentials infrastructure. | 0x4200000000000000000000000000000000000021 |
| SchemaRegistry | Base | Registry for managing attestation schemas and templates. Defines structure for different types of attestations. | 0x4200000000000000000000000000000000000020 |
| CoinbaseIndexer | Base | Coinbase indexing service for attestation data aggregation. Provides efficient querying and discovery of attestations. | 0x2c7eE1E5f416dfF40054c27A62f7B357C4E8619C |
| CoinbaseAttester | Base | Official Coinbase attestation authority and issuer. Creates and validates Coinbase-backed attestations. | 0x357458739F90461b99789350868CD7CF330Dd7EE |
| CoinbaseResolver | Base | Resolver for processing and validating Coinbase attestations. Handles attestation verification and resolution logic. | 0xD867CbEd445c37b0F95Cc956fe6B539BdEf7F32f |

### Coinbase Smart Wallet Infrastructure
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| CoinbaseSmartWalletValidator | Ethereum, Optimism, Arbitrum, Base | Validator contract for Coinbase Smart Wallet transactions. Provides signature verification and security validation. | 0x79A33f950b90C7d07E66950daedf868BD0cDcF96 |
| DefaultReceiver | Ethereum, Base, Arbitrum, Optimism | Default fallback receiver for smart wallet transactions. Handles ETH and token transfers when no specific handler exists. | 0x2a8010A9D71D2a5AEA19D040F8b4797789A194a9 |
| MagicSpend | Base | ERC-4337 paymaster contract with gasless transaction support. Enables sponsored transactions and flexible payment methods. | 0x736b661a643B57F11d131CB3Ae6129C22ea02843, 0xe1D39a19Af4319eBA972fd70A5280CA0aE7cA0AC, 0xF7F64baDcbf64A1DbcAE29C223BE1387F8a301A0, 0x485B2544745786FA2dD95B8C239f6CB3a63D198d, 0xa5b50A9ed69811aFA07151b3B98b8F6B58C5c28A, 0x325A4Af669032B6b1296C3084f8070D04F9AD581, 0xd27D5277215754dc84C8e0736D8fef2Ed39d92F3, 0x53899E2B6C6202C5Eb4F229DA1294F17A0C3876e, 0x7d334106dAa009Ef62CBd34C1624Bee2277bA735, 0xfb1A43620c648A43eEE7bc112db5F2498e619DC5, 0x1d3F02EF7D6881C5018863d740c026639aC7fa41, 0xbd25CE451C24554f53D984b8C64B7A0aBC5FDbB5, 0x5c77CF220dFA3dBBB052D9b4934E61d69cb393a5 |
| TokenFactory | Base | Factory contract for creating and deploying new tokens. Simplifies token creation with standard templates. | 0x0000C479718a45e3D80b9A71C17b2E954CfA1515 |
| SmartWalletFactory | Base | Factory contract for deploying Coinbase Smart Wallets. Handles wallet creation and initialization logic. | 0x0BA5ED0c6AA8c49038F819E587E2633c4A9F428a |
| VerifyingPaymaster V7 | Base | Latest version of verifying paymaster with enhanced security. Validates transactions before sponsoring gas fees. | 0x2FAEB0760D4230Ef2aC21496Bb4F0b47D634FD4c |
| VerifyingPaymaster V6 | Base | Previous version of verifying paymaster for compatibility. Legacy gas sponsorship with basic verification. | 0xa270ef92c1E11f1C1f95753C2E56801e8125fA83 |

### Coinbase Validator Staking Infrastructure
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| BatchDeposit | Ethereum | Batch staking deposit contract for efficiency. Allows multiple validator deposits in single transaction. | 0x8eBda19DdEE719DAB78DEf3e22c3d37970e35217 |

### Commerce Payments
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| AuthCaptureEscrow | Base | Authorized payment capture and escrow management. Securely holds payments pending authorization. | 0xBdEA0D1bcC5966192B070Fdf62aB4EF5b4420cff |
| ERC3009PaymentCollector | Base | ERC-3009 compliant payment collection contract. Handles gasless payments using transferWithAuthorization. | 0x0E3dF9510de65469C4518D7843919c0b8C7A7757 |
| Permit2PaymentCollector | Base | Uniswap Permit2 compatible payment collector. Enables gasless token transfers with signature-based permits. | 0x992476B9Ee81d52a5BdA0622C333938D0Af0aB26 |
| PreApprovalPaymentCollector | Base | Pre-approved payment collection contract. Collects payments from pre-authorized token allowances. | 0x1b77ABd71FCD21fbe2398AE821Aa27D1E6B94bC6 |
| SpendPermissionPaymentCollector | Base | Spend permission-based payment collector. Manages payments through spend permission authorization. | 0x8d9F34934dc9619e5DC3Df27D0A40b4A744E7eAa |
| OperatorRefundCollector | Base | Operator refund collection and processing contract. Handles automated refunds for failed payment operations. | 0x934907bffd0901b6A21e398B9C53A4A38F02fa5d |

### DEX Aggregator
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| ZeroExProxy | Ethereum | 0x Protocol proxy contract for DEX aggregation. Routes trades through multiple decentralized exchanges. | 0x564d6e3A879c007183fAd17beD9A70630F090651 |
| ZeroExProxy | Base | 0x Protocol proxy contract for DEX aggregation. Routes trades through multiple decentralized exchanges. | 0x29ef818a2A9d182Fa9A9D27d61881a239fa03E4B |

### EIP-7702
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| EIP7702Proxy | Ethereum, Arbitrum | EIP-7702 account abstraction proxy implementation. Enables externally owned accounts to delegate to smart contracts. | 0x7702cb554e6bFb442cb743A7dF23154544a7176C |
| NonceTracker | Ethereum, Optimism, Base, Arbitrum | Nonce tracking for EIP-7702 implementations. Manages transaction nonces for account abstraction. | 0xD0Ff13c28679FDd75Bc09c0a430a0089bf8b95a8 |

### Spend Permissions
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| SpendPermissionManager | Ethereum, Base, Optimism, Arbitrum, Polygon | Manages spending permissions for delegated transfers. Enables secure authorization of spending limits and approvals. | 0xf85210B21cC50302F477BA56686d2019dC9b67Ad |
| SpendRouter | Base | Stateless singleton router that pulls tokens from user smart wallets via SpendPermissionManager and forwards them to designated recipients. Routes funds using metadata encoded in SpendPermission extraData field. | 0x1a672dE48c82278b2F1BB68d7b9141634dD6BE29 |
| PublicERC6492Validator | Ethereum, Base, Optimism, Arbitrum, Polygon | ERC-6492 signature validation for smart contract wallets. Validates signatures for undeployed contracts and counterfactual addresses. | 0xcfCE48B757601F3f351CB6f434CB0517aEEE293D |

### Verified Pools
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| SignatureChecker | Base | Signature verification for pool operations. Validates signatures for authorized pool interactions. | 0x2D04d1743BaB35B13841A466788479c591E01381 |
| VerifiedPoolsBasicHook | Base | Basic hook implementation for verified pools. Provides customizable pool behavior and validation logic. | 0x5cd525c621AFCa515Bf58631D4733fbA7B72Aae4 |
| VerifiedPoolsPositionManager | Base | Position management for verified liquidity pools. Handles liquidity positions and fee collection for verified pools. | 0x043ac8DBd2F0e932800210260f207806650C6145 |
| VerifiedPoolsPositionDescriptor | Base | NFT descriptor for verified pool positions. Generates metadata and visuals for liquidity position NFTs. | 0x0705717527934a1E10e5328A0B92462c8eB1A28F |
| RemoveLiquidityPolicy | Base | Policy contract for liquidity removal operations. Enforces rules and restrictions for withdrawing liquidity. | 0x071fF6D93895c8E6537C572a6D40CF47c36aBed7 |
| BasicPolicy | Base | Basic policy implementation for pool operations. Defines standard rules for verified pool interactions. | 0xcC7fE2Cf5B79F3EFaBF42caC8E223813242E1454 |

### Wrapped Tokens (ADA, DOGE, LTC, XRP & Others)
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| coinbase wrapped ada Mint Forwarder | Base | Mint forwarder for Coinbase wrapped Cardano (cbADA). Manages cross-chain minting and burning of wrapped ADA tokens. | 0x8c44C6a9ee7e64a65F288714d1Bb8043Cf0f3C5C |
| coinbase wrapped ada | Base | Coinbase wrapped Cardano token (cbADA). ERC20 representation of ADA bridged to Base network. | 0xcbADA732173e39521CDBE8bf59a6Dc85A9fc7b8c |
| coinbase wrapped doge Mint Forwarder | Base | Mint forwarder for Coinbase wrapped Dogecoin (cbDOGE). Manages cross-chain minting and burning of wrapped DOGE tokens. | 0x0549899a89e661044f9E7a1B76A157d407D85163 |
| coinbase wrapped doge | Base | Coinbase wrapped Dogecoin token (cbDOGE). ERC20 representation of DOGE bridged to Base network. | 0xcbD06E5A2B0C65597161de254AA074E489dEb510 |
| coinbase wrapped ltc Mint Forwarder | Base | Mint forwarder for Coinbase wrapped Litecoin (cbLTC). Manages cross-chain minting and burning of wrapped LTC tokens. | 0x423077A24c3019E3A291bE2D29a34A4D97AA2DeD |
| coinbase wrapped ltc | Base | Coinbase wrapped Litecoin token (cbLTC). ERC20 representation of LTC bridged to Base network. | 0xcb17C9Db87B595717C857a08468793f5bAb6445F |
| coinbase wrapped xrp Mint Forwarder | Base | Mint forwarder for Coinbase wrapped XRP (cbXRP). Manages cross-chain minting and burning of wrapped XRP tokens. | 0x2ebDCFaCCB0c3B6039Dd8C7c30bF633ACE8c268C |
| coinbase wrapped xrp | Base | Coinbase wrapped XRP token (cbXRP). ERC20 representation of XRP bridged to Base network. | 0xcb585250f852C6c6bf90434AB21A00f02833a4af |
| TokenFactory | Base, Ethereum | Factory contract for deploying wrapped token contracts. | 0x0000D340e876e1De249CcA0FD91d91aE612741E8, 0x00003f0f758054D91430AFC79b8666fbA06ccB2c, 0x0000955334545d3c2bdECE50C7F3877054F4dCF7, 0x000036624A21E2047D28449989A943c64b5210d0, 0x00005721895c940fe1066B147358cE6d31A31378, 0x0000B216f5011f882604D2cFa295A83d77025727, 0x0000DfcD0263aC062b3fC7A17aBd1f0407f389A6, 0x00000000001c3dC9A681A014e2732bF1419aFAec (Eth & Base) |
| MintForwarderFactory | Base, Ethereum | Factory for deploying mint forwarder contracts. | 0x000054fCEAB4632B9c8B7fd20cE9790352426716, 0x0000FF0b7Fdf0449c0761356680c0516fD76c0f5, 0x0000F4E1b81A88A7b1732a4A5FdfaA4999F45075, 0x00001962896d81F18Bca192a2Bc90f85b5478698, 0x0000Bfaa45AA7352D7A5b151D34f4EFc096E9Cf6, 0x0000Efa3D0485d3E0B6A48adE0d61a59451f648f, 0x00002027199E51Ce5648E56F0F003759e3D7b16e, 0x0000c1c5F00bD1843b6c1703eA1F457a2Bb5c457, 0x0000000000E552550beC95A36217A91CeBA099b0 (Eth & Base) |
| BatchBlacklister | Base, Ethereum | Batch blacklisting of addresses on FiatToken contracts. | 0x20F25adf31BD5Ed53367293C6926bF1AdfC7Ea54, 0x76D62719c6A7766c8478B46f995E99AD4675d86a, 0x17165086067fc58a04CB8E9dA5B6917B6f23f109, 0xA9A4408db72F168c5b0bf413b369824450517126, 0x4d5b3aca5968f7075F023d2A7AA830358C3c2b48, 0xE3111D45733Efee14bFB1EbE2364D929eDBd9059, 0xadab385DFD0bB2c21E292c5F586471a2878A101e, 0x0C8B7E98b39aA7983D2444661805a628E8A041DB, 0xF903f3A8B30a7b645e76DB8511b4121cc96160EB (Eth & Base) |
| BatchBlacklisterV2 | Base, Ethereum, Arbitrum | Enhanced batch blacklisting with additional features. | 0xa0BF66C54002cEb15aB6E8423EebB994E8b2f7FE (Base), 0xE34Fd8e02815125aB0947434e42978a8A4e70906 (Eth), 0x63d7212C0503b04BdC2BCCe90fe26800859F2f81 (Arb) |
| MintFactoryFree | Base | Free tier factory for token minting operations. | 0x5da05215acA9eDBE27CBDCE86888986E4b4c996F |
| MintFactory | Base | Factory contract for deploying mintable token contracts. | 0x20e26eD291B85A44A6Eb9b0D336512b53fd93092, 0x560aa3207ae4b516A5489E04f2Fa2e2808CEa896 |
| MintFactoryCreator | Base | Meta-factory for creating MintFactory instances. | 0xAeb73b6C8ed3776EA6b9284082588c55E35e1b27, 0x52d443855E4d15dc47d323fA94e7d92342d3Eb57 |

### Liqufi
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| WeightedTokenVestingLockup | Ethereum, Arbitrum, Avalanche, Base, Polygon, Optimism | Token vesting contract with weighted release schedules. | 0xb7486B5bd2d14714950B082EafebE9822a1d96eE (Eth), 0xaa861940DD2ED2fE4a3108E51f7f117bb6798E65 (Arb), 0xB487A8739AA114178C5aA5608eF1D2fc26D17A9e (Avax), 0x2A06274c976C4db9CbaF702B559E0B5765D07b0d (Base), 0x9efea6f63d583624E5a459D680D3A27Adf6C570d (Polygon), 0x16879Ca809e8CA2783d89C2Ee830671A8C348230 (OP) |
| WeightedTokenVestingLockupFactory | Ethereum, Arbitrum, Avalanche, Base, Polygon, Optimism | Factory contract for deploying WeightedTokenVestingLockup instances. | 0x341251e680fB0FD4f47aD4dC1AD61C3bE5142d0e (Eth), 0xD42eA6a51ec16c0Cb581695343F9F3d652d98945 (Arb), 0x5bFd3bDFf68346909d352757055e98f2654a3c10 (Avax), 0x08c1820bA6A0B88eB1f3E3eC7C9B8cf85E63C6FC (Base), 0xc7284314593e952717b6a0b78766887b37fb1720 (Polygon), 0x85F2A6BB58E52c9189fD8748790C5059508FBDc1 (OP) |
| WeightedVestingModule | Ethereum, Arbitrum, BNB Smart Chain, Avalanche, Base, Polygon, Optimism | Modular vesting component with customizable weight parameters. | 0xc76B81D835A6Ef88fb9b841C22Ed492473577aC3 (Eth), 0xF3D74Bc4E97aD56DDcB0576629c360fB40A871e2 (Arb), 0x3065aa025a27B42B98E43a5fF7B3965c0174D1bD (BNB), 0xD85d9Cd1E453AeE54e448Cef4941F0718922a672 (Avax), 0xcc93eb838F061A375A37d0d65E8D68f15e9D07E5 (Base), 0x595db8eCa8d64f28A57D5F240204FDc8AdbCb8c7 (Polygon), 0x848E9743b6D0aC5614f6427d94fEd295Fe393b6d (OP) |
| VestingModuleRegistry | Ethereum, Arbitrum, BNB Smart Chain, Avalanche, Base, Polygon, Optimism | Central registry for managing and discovering vesting modules. | 0x782F402C93E9b0d931197cD727e006356B55699d (Eth), 0x6A46c2411e6FD9205D44b82C5B32B2Db7C150263 (Arb), 0x208F9c3Ca561977ee49AB84E2243c1531a265bd1 (BNB), 0xE57499B85448582a0bFd486283a0a023581D2778 (Avax), 0x674A3Ab5d2be0dA09bF1662E1f9827bdDA3d103F (Base), 0x00F849ca595cFa7CeCd052E77e9d152618333E8E (Polygon), 0xC34c1643c4C2488315Dc709FCB5ABc6b4E3dE6C7 (OP) |
| BatchPayments | Ethereum, Arbitrum, BNB Smart Chain, Avalanche, Base, Polygon, Optimism | Efficient batch payment processor for multiple recipients. | 0x39C4B71D53Db0B6B647fe5013608eeA292db4A73 (Eth, Arb, BNB, Avax, Polygon, OP), 0x834297cAF503d9455395A62336e653FCf2234962 (Base) |
| WeightedTokenVesting (v1) | BNB Smart Chain | Legacy v1 token vesting contract with basic functionality. | 0x674A3Ab5d2be0dA09bF1662E1f9827bdDA3d103F |
| WeightedTokenVestingFactory (v1) | BNB Smart Chain | Legacy v1 factory for creating basic vesting contracts. | 0x834297cAF503d9455395A62336e653FCf2234962 |

### Base <> Solana Bridge
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| Bridge | Base | Core bridge contract for Base-Solana cross-chain messaging. Handles message passing and asset transfers between chains. | 0x3eff766C76a1be2Ce1aCF2B69c78bCae257D5188 |
| BridgeValidator | Base | Validator contract for cross-chain message verification. Validates signatures and proofs from Solana. | 0xAF24c1c24Ff3BF1e6D882518120fC25442d6794B |
| CrossChainERC20Factory | Base | Factory for deploying cross-chain ERC20 tokens. Creates wrapped token representations of Solana assets on Base. | 0xDD56781d0509650f8C2981231B6C917f2d5d7dF2 |
| Twin Beacon | Base | Beacon proxy for upgradeable twin token contracts. Manages implementation upgrades for cross-chain tokens. | 0xb326c02150bb0De265Bb0eCeDA53531ab0163bf6 |
| Twin Implementation | Base | Implementation contract for twin tokens. Contains core logic for cross-chain token operations. | 0xb0887e4793d944Cf7bA674B3b3FA5C15900ddaA7 |
| Solana Bridge Program | Solana | Core Solana program for Base-Solana bridging. Handles message validation and token custody on Solana. | HNCne2FkVaNghhjKXapxJzPaBvAKDG1Ge3gqhZyfVWLM |
| Relayer | Solana | Relayer account for cross-chain message delivery. Submits transactions on Solana for bridged messages from Base. | g1et5VenhfJHJwsdJsDbxWZuotD5H4iELNG61kS4fb9 |

### Echo
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| DistributorFactory | Base, BNB Smart Chain, Ethereum, Optimism, ZKSync Era | Factory contract for deploying token distributor proxies. Creates customizable distribution contracts for token vesting and airdrops. | 0x3002aadad07ab12e5bb8098de3542bee2ad44fed (Base), 0x985a20e7bec906778f811799aebf50f90d10f71b (BNB), 0xd6d4b339b972c7dfa427b6818396aeabb5bc03b9 (Eth), 0x2fbdd01e44513302bb2789302e98749fb01c0e8d (OP), 0xa9311c40e4038f6c9597aa07fddd643ae6147d08 (zkSync) |
| Distributor Implementation | Base, BNB Smart Chain, Ethereum, Optimism, ZKSync Era | Core implementation contract for token distribution logic. | 0x1798D23f29968b4fff7A60A90645B0939d04f47E (Base), 0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF (Base), 0x5cDf694C5bE8B9E83663e16eFA8a09FE284b3238 (BNB), 0x103937F52B9E8Fdd370845E049F3601c2979890a (BNB), 0x900857be98cd16C97f270Ce450169761858eb559 (Eth), 0xF9456B2d7EA7CDD9accAa89771DD9E9709C5bB6a (OP), 0xB3678A158E83946D02eaBa654a1a6e8eA4d6889C (OP), 0xAbf8fcD8954Af787A8f7c080D10E7AcD7BD1F5B5 (zkSync) |
| GenericRegistry | Base, BNB Smart Chain, Ethereum, Optimism | Central registry for tracking deployed distributor contracts. | 0x73612914c81a9c072333ea9ea71a9b26a5b9a707 (Base), 0x198cbbf1232bb033268a7276ca91d1f3cd4cb896 (BNB), 0xd643980ee0ef698d37217d8f0123b0f766adec71 (Eth), 0x84730533ed3d4dcbac265976a5d7ef47ad2e1e9f (OP) |
| DealFactory | Base | Factory contract for deploying deal contracts. Creates OTC deal structures for token sales and agreements. | 0x475ddcfd166b80d41d2778ec3a8fa8bbcc887095 |
| Deal Implementation | Base | Core implementation for deal contract logic. Handles deal execution, escrow, and settlement mechanics. | 0x65cDabC9EbF1DfB72600754aa98F90A2EA285Eba |
| Settlement | Base | Settlement contract for finalizing deal transactions. Manages fund transfers and deal completion logic. | 0x7263056963E131153927234e0Ce1457a32D888a4 |
| FunderIntegration | Base | Integration contract for funding operations. Connects external funding sources to distribution contracts. | 0x5D09B26B148f9b9e341E9DB8116e3DFa7755CFd6 |
| ERC20PermitFundingConduit | Base | Funding conduit with ERC20 permit support. Enables gasless token approvals for funding operations. | 0x29BEa561cb302FD2B85F5c0c6086BE8b1560F2df |
| MultiChainWithdrawer | Base | Cross-chain withdrawal management contract. Handles token withdrawals across multiple blockchain networks. | 0x5fd109945d80fd2e54ffa331ebfe18ca301f2a67 |
| Linear Unlocker | Base | Linear token unlocking contract for vesting schedules. Releases tokens gradually over a defined time period. | 0x166415114ef0f243e1bba193df3862b78c13521f, 0xbceb8401e7a6b3b35ab15d94c369aa7863b550a9 |

### Flywheel Protocol
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| Flywheel | Base | Core protocol orchestrator for modular rewards and attribution. Manages campaign lifecycle, payout operations (send, allocate, distribute, deallocate), and fund custody via isolated Campaign clones. | 0x00000f14ad09382841db481403d1775adee1179f |
| AdConversion | Base | Attribution-based advertising campaign hook. Processes publisher conversions with configurable attribution windows, publisher allowlists, and attribution provider fee structures. | 0x5a178f113d9851c72c63e7f58255d4520c1a1d9d |
| SimpleRewards | Base | Manager-controlled rewards hook with minimal validation. Supports send, allocate, deallocate, and distribute payout operations for flexible reward distribution. | 0x58c5fa1e6e651320499ccfb2198ede481b35c87b |
| BuilderCodes | Base | UUPS upgradeable publisher registry managing referral code identities as ERC721 NFTs. Maps publisher codes to payout addresses and controls all publisher payouts across the protocol. | 0x000000bc7e6457e610fe52dcc0ca5b3ce59c8e80 |

### Recovery Signer
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| RecoverySignerFactory | Base | Factory for deploying per-user RecoverySigner contracts (EIP-1167 minimal clones). Guardian-based social recovery for Coinbase retail smart wallets. Each RecoverySigner is owned by a Coinbase K2 guardian key and can add/remove owners on the user's smart wallet. | 0xf3Ef80A7664c286997B35b0D1a6d56A9008F9336 |

### Tokenized Equities
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| TokenSupplyManager | Base | Sole holder of MINT_ROLE and BURN_ROLE on every tokenized equity; all issuance and redemption funnels through it. Enforces per-caller rolling mint rate limits and gates redemption on a PolicyRegistry allowlist. UUPS proxy — proxy listed first, current implementation second. | 0xD1Ca4dAcdf3231011D175351f1f02D15C7c5664C (Proxy), 0x3F27d252526470a04D6222252E37B84580A4C6E3 (Impl) |
| B20AssetFactory | Base | Role-gated UUPS wrapper around the Base B20 token factory precompile that deploys each equity token. Binds every new token to the TokenSupplyManager and to the transfer policy at creation time. Proxy listed first, current implementation second. | 0x4bA3E29E254F25E94E61C4c9d67b37027331534D (Proxy), 0xbBcb88b1E706624D7FB631b0b2557a173eF028Ca (Impl) |
| OracleRegistry | Base | Published by Base as the “Onchain Registry”. Returns a token’s multiplier and pause flag in a single call. The Chainlink total-return price feeds for every tokenized equity read this contract, so a wrong multiplier or a stuck pause flag propagates directly into published prices. | 0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD |

## Out of Scope
### Out of Scope Targets
The following types of contracts will not be in scope:
- Contracts deployed on testnets and devnets
- Contracts deployed on mainnet for testing purposes
- Contracts deployed on mainnet for internal use
- Third-party dependencies of any of our contracts
- Third-party contracts that may be used by Coinbase to provide certain services

### Default Out of Scope
- Issues found in previous security reviews
- Third-party contracts not under direct project control
- Issues with non-standard ERC20 tokens (unless explicitly supported by the project)
- Rounding errors with no significant impact
- User errors requiring obviously incorrect parameter inputs
- Vulnerabilities that only manifest during extreme market conditions
- Incorrect data from third-party oracles (Note: Oracle manipulation and flash loan attacks are still in scope)
- Theoretical exploits without practical proof-of-concept
- Issues requiring access to leaked keys or credentials
- Issues arising from Sybil attacks
- Centralization risks
- Basic economic and governance attacks (such as 51% attacks)
- Protocol design choices
- Gas optimization issues and high gas costs
- Best practice suggestions
- Submissions generated using ChatGPT or other LLM tools
<!-- SCOPE END -->

## Scope Verification Digest
- **SHA-256 (LF):** `6152de2e2ff2fd68fd25f3fd4a8cd4c23639dc5dcb3bb2754d9eaad2b1cff3f9`
- **Computed:** 2026-10-11
