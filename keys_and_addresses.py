# IMPORTANT: Replace these values with your own private keys and addresses
# DO NOT share your actual private keys with anyone!

# List of private keys for your wallets
private_keys = [
    "YOUR_PRIVATE_KEY_1",  # Wallet 1
    "YOUR_PRIVATE_KEY_2",  # Wallet 2
    # Add more private keys as needed
]

# List of wallet addresses corresponding to the private keys
my_addresses = [
    "YOUR_WALLET_ADDRESS_1",  # Address for Wallet 1
    "YOUR_WALLET_ADDRESS_2",  # Address for Wallet 2
    # Add more addresses as needed
]

# Optional labels for your wallets
labels = [
    "Wallet 1",
    "Wallet 2",
    # Add more labels as needed
]

# Ensure the number of private keys matches the number of addresses
assert len(private_keys) == len(my_addresses), "Number of private keys must match number of addresses"
assert len(labels) == len(my_addresses), "Number of labels must match number of addresses"
