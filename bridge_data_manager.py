import requests
import json
from typing import Dict, Optional
from bs4 import BeautifulSoup

class BridgeDataManager:
    def __init__(self):
        self.op_contract = "0xF221750e52aA080835d2957F2Eed0d5d7dDD8C38"
        self.base_contract = "0x30A0155082629940d4bd9Cd41D6EF90876a0F1b5"
        self.op_api_url = "https://optimism-sepolia.blockscout.com/api/v2/addresses/"
        self.base_api_url = "https://base-sepolia.blockscout.com/api/v2/addresses/"
        self.method_id = "0x56591d59"
        
    def _get_latest_tx_input(self, api_url: str, contract_address: str) -> Optional[str]:
        """Fetch the latest transaction input data for a contract with specific method ID"""
        try:
            url = f"{api_url}{contract_address}/transactions"
            print(f"\nFetching from: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            if data.get("items"):
                # Look through transactions for our method
                for tx in data["items"]:
                    raw_input = tx.get("raw_input")
                    if raw_input and len(raw_input) == 458 and raw_input.startswith(self.method_id):
                        # Validate OP-Base specific identifiers
                        if (contract_address == self.op_contract and "62737370" in raw_input[10:18]) or \
                           (contract_address == self.base_contract and "6f707370" in raw_input[10:18]):
                            print(f"Found valid bridge transaction")
                            return raw_input
                print(f"No valid bridge transactions found")
            return None
        except Exception as e:
            print(f"Error fetching latest transaction: {str(e)}")
            return None

    def _update_input_data(self, input_data: str, wallet_address: str) -> str:
        """Update the input data with the new wallet address"""
        try:
            # Remove '0x' prefix from wallet address for consistency
            clean_address = wallet_address[2:].lower()
            
            # Replace the address in the input data
            start_pos = 162
            end_pos = 201
            updated_data = (
                input_data[:start_pos] +
                clean_address +
                input_data[end_pos+1:]
            )
            
            return updated_data
            
        except Exception as e:
            print(f"Error updating input data: {str(e)}")
            return None

    def get_updated_bridge_data(self, wallet_address: str) -> Dict[str, str]:
        """Get updated bridge data for both chains"""
        print("\nFetching latest transaction data from contracts...")
        
        # Get latest transaction data from both chains
        op_input = self._get_latest_tx_input(self.op_api_url, self.op_contract)
        base_input = self._get_latest_tx_input(self.base_api_url, self.base_contract)
        
        bridge_data = {}
        
        if op_input:
            updated_op_data = self._update_input_data(op_input, wallet_address)
            bridge_data["OP - BASE"] = updated_op_data
            print(f"\nOptimism to Base Input Data updated")
            
        if base_input:
            updated_base_data = self._update_input_data(base_input, wallet_address)
            bridge_data["BASE - OP"] = updated_base_data
            print(f"\nBase to Optimism Input Data updated")
            
        return bridge_data

    def update_data_bridge(self, wallet_address: str) -> Dict[str, str]:
        """Update the data_bridge.py file with new bridge data and return the updated data"""
        try:
            bridge_data = self.get_updated_bridge_data(wallet_address)
            
            if not bridge_data:
                print("No new bridge data available")
                return {}
                
            # Read the current content of data_bridge.py
            with open('data_bridge.py', 'r') as file:
                content = file.read()
                
            # Update the bridge data
            for bridge_type, input_data in bridge_data.items():
                if input_data:
                    # Create the new data string
                    new_data = f'    "{bridge_type}": \'{input_data}\''
                    
                    # Find and replace the existing data
                    import re
                    pattern = f'"{bridge_type}":.+?\n'
                    content = re.sub(pattern, new_data + ',\n', content)
            
            # Write the updated content back to the file
            with open('data_bridge.py', 'w') as file:
                file.write(content)
                
            print("\nBridge data updated successfully")
            return bridge_data
        except Exception as e:
            print(f"Error updating bridge data: {str(e)}")
            return {}

    def bridge_transaction(self, web3, contract, input_data: str) -> bool:
        """Execute a bridge transaction with the given input data"""
        try:
            # Get the transaction count
            nonce = web3.eth.get_transaction_count(web3.eth.default_account)
            
            # Prepare the transaction
            transaction = {
                'from': web3.eth.default_account,
                'to': contract.address,
                'value': 0,
                'nonce': nonce,
                'data': input_data,
                'chainId': web3.eth.chain_id
            }
            
            # Estimate gas and set gas parameters
            try:
                gas_estimate = web3.eth.estimate_gas(transaction)
                transaction['gas'] = int(gas_estimate * 1.2)  # Add 20% buffer
                transaction['maxFeePerGas'] = web3.eth.max_priority_fee
                transaction['maxPriorityFeePerGas'] = web3.eth.max_priority_fee
            except Exception as e:
                print(f"Error estimating gas: {str(e)}")
                return False
            
            # Sign and send the transaction
            signed_txn = web3.eth.account.sign_transaction(transaction, private_key=web3.eth.account.privateKey)
            tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"\n🔄 Transaction sent! Hash: {tx_hash.hex()}")
            print("⏳ Waiting for confirmation...")
            
            # Wait for transaction receipt
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt['status'] == 1:
                print("✅ Transaction confirmed!")
                return True
            else:
                print("❌ Transaction failed!")
                return False
                
        except Exception as e:
            print(f"❌ Error executing bridge transaction: {str(e)}")
            return False

    def execute_bridge(self, web3, contract, bridge_type: str) -> bool:
        """Execute a bridge operation with fresh input data"""
        try:
            # Get fresh bridge data before each transaction
            bridge_data = self.get_updated_bridge_data(web3.eth.default_account.address)
            
            if not bridge_data or bridge_type not in bridge_data:
                print(f"❌ No valid bridge data available for {bridge_type}")
                return False
                
            input_data = bridge_data[bridge_type]
            print(f"\nUsing input data for {bridge_type} bridge")
            
            # Execute the bridge transaction
            return self.bridge_transaction(web3, contract, input_data)
            
        except Exception as e:
            print(f"❌ Error during bridge execution: {str(e)}")
            return False
