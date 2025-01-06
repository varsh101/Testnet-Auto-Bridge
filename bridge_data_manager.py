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
            clean_address = wallet_address[2:].lower()
            
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
            return input_data

    def get_bridge_data(self, wallet_address: str) -> Dict[str, str]:
        """Get bridge data for both directions"""
        bridge_data = {}
        
        # Get OP to Base data
        op_input = self._get_latest_tx_input(self.op_api_url, self.op_contract)
        if op_input:
            bridge_data["OP - BASE"] = self._update_input_data(op_input, wallet_address)
        
        # Get Base to OP data
        base_input = self._get_latest_tx_input(self.base_api_url, self.base_contract)
        if base_input:
            bridge_data["BASE - OP"] = self._update_input_data(base_input, wallet_address)
        
        return bridge_data
