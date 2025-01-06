import requests
import json
import time
import random
import threading
from network_config import networks

# Bridge data
data_bridge = {
    # Default bridge data as fallback
    "OP - BASE": '0x56591d5962737370000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000016345785d8a0000',
    "BASE - OP": '0x56591d596f707370000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000016345785d8a0000'
}

def update_bridge_data(address):
    """Update bridge data by fetching latest transactions from Blockscout"""
    try:
        print("\n📥 Fetching bridge data...")
        op_url = f"https://optimism-sepolia.blockscout.com/api/v2/addresses/{networks['OP Sepolia']['contract_address']}/transactions?filter=to"
        
        try:
            op_response = requests.get(op_url, timeout=10)
            
            if op_response.status_code == 200:
                op_txs = op_response.json()['items']
                
                for tx in op_txs:
                    if tx.get('status') != '1':
                        continue
                        
                    input_data = tx.get('raw_input') or tx.get('input')
                    if input_data and len(input_data) >= 100:
                        if input_data != data_bridge["OP - BASE"]:
                            data_bridge["OP - BASE"] = input_data
                            print("Optimism to Base Input Data updated")
                        break
            else:
                print(f"⚠️ Failed to fetch OP data: {op_response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error fetching OP data: {str(e)}")
            
        # Fetch Base to OP data
        base_url = f"https://base-sepolia.blockscout.com/api/v2/addresses/{networks['Base Sepolia']['contract_address']}/transactions?filter=to"
        
        try:
            base_response = requests.get(base_url, timeout=10)
            
            if base_response.status_code == 200:
                base_txs = base_response.json()['items']
                
                for tx in base_txs:
                    if tx.get('status') != '1':
                        continue
                        
                    input_data = tx.get('raw_input') or tx.get('input')
                    if input_data and len(input_data) >= 100:
                        if input_data != data_bridge["BASE - OP"]:
                            data_bridge["BASE - OP"] = input_data
                            print("Base to Optimism Input Data updated")
                        break
            else:
                print(f"⚠️ Failed to fetch Base data: {base_response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error fetching Base data: {str(e)}")
            
    except Exception as e:
        print(f"⚠️ Error updating bridge data: {str(e)}")

class BalanceTracker:
    def __init__(self, web3, address):
        self.web3 = web3
        self.address = address
        self.balances = {
            'op': None,  # Optimism balance
            'base': None,  # Base balance
        }
        self.ongoing_bridges = {
            'op_to_base': [],  # List of amounts being bridged from OP to Base
            'base_to_op': []   # List of amounts being bridged from Base to OP
        }
        self.failed_checks = 0
        self.paused = False
        self.pause_until = 0
        self.min_expected_balance_change = 0.05  # Minimum expected balance change (ETH)
        self.last_check_time = 0
        self.monitor_thread = None
        self.stop_monitoring = False
        self.chain_web3 = {
            'op': None,    # Will be set when switching chains
            'base': None   # Will be set when switching chains
        }
        self.monitoring_active = False  # New flag to control monitoring state
        self.pause_duration = 30  # Pause duration in minutes
        self.check_interval = 120  # Balance check interval in seconds
        self.max_failed_checks = 2  # Number of failed checks before pausing

    def set_chain_web3(self, chain, web3_instance):
        """Set web3 instance for a specific chain"""
        self.chain_web3[chain] = web3_instance

    def update_balance(self, chain):
        """Get current balance in ETH for specified chain"""
        try:
            if self.chain_web3[chain]:
                balance = self.chain_web3[chain].eth.get_balance(self.address)
                return float(self.chain_web3[chain].from_wei(balance, 'ether'))
        except Exception as e:
            print(f"⚠️ Error getting {chain} balance: {str(e)}")
        return None

    def start_bridge(self, amount, from_chain, to_chain):
        """Register a new ongoing bridge with chain direction"""
        if from_chain == 'op' and to_chain == 'base':
            self.ongoing_bridges['op_to_base'].append(amount)
        elif from_chain == 'base' and to_chain == 'op':
            self.ongoing_bridges['base_to_op'].append(amount)
        else:
            print(f"⚠️ Invalid bridge direction: {from_chain} -> {to_chain}")

    def start_monitoring(self):
        """Start the continuous balance monitoring thread"""
        if not self.monitoring_active:
            print("📊 Starting balance monitoring thread...")
            self.stop_monitoring = False
            self.monitoring_active = True
            self.last_check_time = time.time()  # Set initial check time to now
            self.monitor_thread = threading.Thread(target=self._monitor_balance)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            print("📊 Balance monitoring thread started")
            print(f"✅ Balance monitoring activated (checking every {self.check_interval} seconds)")

    def stop_monitoring_thread(self):
        """Stop the monitoring thread safely"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.stop_monitoring = True
            self.monitoring_active = False
            self.monitor_thread.join(timeout=5)
            print("📊 Balance monitoring stopped")

    def _monitor_balance(self):
        """Continuous balance monitoring function for both chains"""
        while not self.stop_monitoring:
            current_time = time.time()
            time_since_last_check = current_time - self.last_check_time
            
            if time_since_last_check >= self.check_interval:
                if len(self.ongoing_bridges['op_to_base']) > 0 or len(self.ongoing_bridges['base_to_op']) > 0:
                    print(f"\n⏰ Balance check interval reached ({self.check_interval}s)")
                    print("🔄 Active bridges found, performing balance check...")
                    
                    if self.check_all_bridges():
                        self.last_check_time = current_time
            
            time.sleep(1)  # Small sleep to prevent CPU overuse

    def check_all_bridges(self):
        """Check bridges on both chains"""
        if self.paused:
            remaining_pause = max(0, self.pause_until - time.time())
            if remaining_pause > 0:
                print(f"⏳ Bridge monitoring paused. Resuming in {remaining_pause:.0f} seconds...")
                return False
            print("✅ Bridge pause period completed. Resuming operations...")
            self.paused = False
            self.failed_checks = 0
            return True

        print("\n🔍 Starting balance check...")
        
        current_balances = {
            'op': self.update_balance('op'),
            'base': self.update_balance('base')
        }
        
        if None in current_balances.values():
            print("⚠️ Skipping check - Could not get balances for all chains")
            return True

        print(f"💰 Current balances:")
        print(f"   OP: {current_balances['op']:.6f} ETH")
        print(f"   Base: {current_balances['base']:.6f} ETH")
        
        changes_detected = False
        
        for amount in list(self.ongoing_bridges['op_to_base']):
            if current_balances['base'] > (self.balances['base'] or 0):
                increase = current_balances['base'] - (self.balances['base'] or 0)
                print(f"✅ Balance increase detected on Base: +{increase:.6f} ETH")
                
                if abs(increase - amount) <= 0.05:
                    self.ongoing_bridges['op_to_base'].remove(amount)
                    changes_detected = True
                    print(f"🌉 Bridge completed: OP -> Base | Amount: {amount:.6f} ETH")
                    print(f"📊 Balance Change: {increase:.6f} ETH")
                else:
                    print(f"⚠️ Balance increase {increase:.6f} ETH doesn't match expected {amount:.6f} ETH")
        
        for amount in list(self.ongoing_bridges['base_to_op']):
            if current_balances['op'] > (self.balances['op'] or 0):
                increase = current_balances['op'] - (self.balances['op'] or 0)
                print(f"✅ Balance increase detected on OP: +{increase:.6f} ETH")
                
                if abs(increase - amount) <= 0.05:
                    self.ongoing_bridges['base_to_op'].remove(amount)
                    changes_detected = True
                    print(f"🌉 Bridge completed: Base -> OP | Amount: {amount:.6f} ETH")
                    print(f"📊 Balance Change: {increase:.6f} ETH")
                else:
                    print(f"⚠️ Balance increase {increase:.6f} ETH doesn't match expected {amount:.6f} ETH")
        
        if not changes_detected and (len(self.ongoing_bridges['op_to_base']) > 0 or len(self.ongoing_bridges['base_to_op']) > 0):
            self.failed_checks += 1
            print(f"⚠️ No balance changes detected. Check #{self.failed_checks}/{self.max_failed_checks}")
            print("🕵️ Ongoing bridges:")
            print(f"   OP -> Base: {len(self.ongoing_bridges['op_to_base'])} bridges")
            print(f"   Base -> OP: {len(self.ongoing_bridges['base_to_op'])} bridges")
            
            if self.failed_checks >= self.max_failed_checks:
                print(f"🛑 Multiple checks failed. Pausing for {self.pause_duration} minutes...")
                self.paused = True
                self.pause_until = time.time() + (self.pause_duration * 60)
                return False
        else:
            if not changes_detected:
                print("✅ No pending bridges to check")
            self.failed_checks = 0
        
        self.balances = current_balances
        print("✅ Balance check completed\n")
        return True

def parse_input(prompt, input_type="time"):
    """Simplified input parser for both time and transaction counts"""
    while True:
        try:
            user_input = input(prompt).strip().lower()
            
            if user_input == 'r':
                if input_type == "time":
                    min_val = int(input("Enter minimum time (seconds): "))
                    max_val = int(input("Enter maximum time (seconds): "))
                    if min_val > max_val:
                        min_val, max_val = max_val, min_val
                    return ('random', (min_val, max_val))
                else:  # transaction count
                    min_val = int(input("Enter minimum transactions: "))
                    max_val = int(input("Enter maximum transactions: "))
                    if min_val > max_val:
                        min_val, max_val = max_val, min_val
                    return ('random', (min_val, max_val))
            
            elif user_input == 'inf' and input_type == "transactions":
                return ('infinite', None)
            
            else:
                value = int(user_input)
                if value < 0:
                    raise ValueError("Value must be positive")
                return ('fixed', value)
                
        except ValueError as e:
            print(f"⚠️ Invalid input: {str(e)}")

def get_random_pause(min_time, max_time):
    """Generate a random pause duration between min and max seconds"""
    return random.uniform(min_time, max_time)
