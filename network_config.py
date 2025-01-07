# network_config.py

networks = {
    'Arbitrum Sepolia': {
        'rpc_url': 'https://sepolia-rollup.arbitrum.io/rpc',
        'chain_id': 421614,
        'contract_address': '0x8D86c3573928CE125f9b2df59918c383aa2B514D'
    },
    'OP Sepolia': {
        'rpc_url': 'https://optimism-sepolia.drpc.org',
        'backup_rpc_urls': [
            'https://sepolia.optimism.io',
            'https://optimism-sepolia.publicnode.com',
            'https://optimism-sepolia.blockpi.network/v1/rpc/public'
        ],
        'chain_id': 11155420,
        'contract_address': '0xF221750e52aA080835d2957F2Eed0d5d7dDD8C38',
        'explorer_url': 'https://optimism-sepolia.blockscout.com'
    },
    'Blast Sepolia': {
        'rpc_url': 'https://blast-sepolia.blockpi.network/v1/rpc/public',
        'chain_id': 168587773,
        'contract_address': '0x1D5FD4ed9bDdCCF5A74718B556E9d15743cB26A2'
    },
    'Base Sepolia': {
        'rpc_url': 'https://base-sepolia-rpc.publicnode.com',
        'backup_rpc_urls': [
            'https://sepolia.base.org',
            'https://base-sepolia.publicnode.com',
            'https://base-sepolia.blockpi.network/v1/rpc/public'
        ],
        'chain_id': 84532,
        'contract_address': '0x30A0155082629940d4bd9Cd41D6EF90876a0F1b5',
        'explorer_url': 'https://base-sepolia.blockscout.com'
    }
}

# RPC request configuration
rpc_config = {
    'timeout': 20,  # reduced timeout for faster fallback
    'retry_count': 2,
    'retry_delay': 1  # reduced delay for faster fallback
}
