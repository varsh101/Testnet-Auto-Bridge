import requests
import json
import time
import random
import threading
from network_config import networks

# Bridge data
data_bridge = {
    # Default bridge data as fallback
                                                                                                                                                                                            "OP - BASE": '0x56591d59627373700000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006d5dba08a0d8490e817094571e5c63e02d3038020000000000000000000000000000000000000000000000000186897c48db5fca000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000186cc6acd4b0000',
                                                                                                                                                                                            "BASE - OP": '0x56591d596f7073700000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000006d5dba08a0d8490e817094571e5c63e02d3038020000000000000000000000000000000000000000000000000162901b091308e200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000016345785d8a0000',
}

def update_bridge_data(address):
    """Update bridge data by fetching latest transactions from Blockscout"""
    try:
        # Fetch OP to Base data
        print("\n📥 Fetching bridge data...")
        op_url = f"https://optimism-sepolia.blockscout.com/api/v2/addresses/{networks['OP Sepolia']['contract_address']}/transactions?filter=to"
        
        try:
            op_response = requests.get(op_url, timeout=10)  # 10 second timeout
            
            if op_response.status_code == 200:
                op_txs = op_response.json()['items']
                
                # Get the most recent successful transaction
                for tx in op_txs:
                    if tx.get('status') != '1':  # Skip failed transactions
                        continue
                        
                    input_data = tx.get('raw_input') or tx.get('input')
                    if input_data and len(input_data) >= 100:  # Basic validation
                        if input_data != data_bridge["OP - BASE"]:  # Only update if different
                            data_bridge["OP - BASE"] = input_data
                            print("✅ Updated OP to Base bridge data")
                        break
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error fetching OP to Base data: {str(e)}")
        
        # Fetch Base to OP data
        base_url = f"https://base-sepolia.blockscout.com/api/v2/addresses/{networks['Base Sepolia']['contract_address']}/transactions?filter=to"
        
        try:
            base_response = requests.get(base_url, timeout=10)  # 10 second timeout
            
            if base_response.status_code == 200:
                base_txs = base_response.json()['items']
                
                # Get the most recent successful transaction
                for tx in base_txs:
                    if tx.get('status') != '1':  # Skip failed transactions
                        continue
                        
                    input_data = tx.get('raw_input') or tx.get('input')
                    if input_data and len(input_data) >= 100:  # Basic validation
                        if input_data != data_bridge["BASE - OP"]:  # Only update if different
                            data_bridge["BASE - OP"] = input_data
                            print("✅ Updated Base to OP bridge data")
                        break
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error fetching Base to OP data: {str(e)}")

    except Exception as e:
        print(f"❌ Error updating bridge data: {str(e)}")
        print("ℹ️ Using fallback bridge data")
        return False

    return True

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
        self.pause_duration = 5  # Pause duration in minutes
        self.check_interval = 60  # Balance check interval in seconds
        self.max_failed_checks = 2  # Number of failed checks before pausing

    def set_chain_web3(self, chain, web3_instance):
        """Set web3 instance for a specific chain"""
        self.chain_web3[chain] = web3_instance
        if self.balances[chain] is None:
            self.balances[chain] = self.update_balance(chain)

    def update_balance(self, chain):
        """Get current balance in ETH for specified chain"""
        if self.chain_web3[chain] is None:
            print(f"⚠️ No Web3 connection for {chain.upper()}")
            return None
        
        retries = 3
        for attempt in range(retries):
            try:
                balance = self.chain_web3[chain].eth.get_balance(self.address)
                eth_balance = float(self.chain_web3[chain].from_wei(balance, 'ether'))
                return eth_balance
            except Exception as e:
                if attempt < retries - 1:
                    print(f"⚠️ Retry {attempt + 1}/{retries} getting {chain.upper()} balance: {e}")
                    time.sleep(2)
                else:
                    print(f"❌ Error getting {chain.upper()} balance after {retries} attempts: {e}")
                    return None

    def start_bridge(self, amount, from_chain, to_chain):
        """Register a new ongoing bridge with chain direction"""
        bridge_key = f"{from_chain}_to_{to_chain}"
        self.ongoing_bridges[bridge_key].append(amount)
        
        # Update source chain balance if needed
        if self.balances[from_chain] is None:
            self.balances[from_chain] = self.update_balance(from_chain)
        
        print(f"📊 Starting bridge from {from_chain.upper()} to {to_chain.upper()} | Amount: {amount:.6f} ETH")
        print(f"💰 Current balances - {from_chain.upper()}: {self.balances[from_chain]:.6f} ETH")
        
        # Start monitoring if not already active
        if not self.monitoring_active:
            self.monitoring_active = True
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                print("📊 Starting balance monitoring thread...")
                self.start_monitoring()
                print(f"✅ Balance monitoring activated (checking every {self.check_interval} seconds)")
            else:
                print("ℹ️ Monitoring thread already running")
        else:
            print("ℹ️ Monitoring already active")

    def _monitor_balance(self):
        """Continuous balance monitoring function for both chains"""
        while not self.stop_monitoring:
            current_time = time.time()
            time_since_last_check = current_time - self.last_check_time
            
            if time_since_last_check >= self.check_interval:
                if len(self.ongoing_bridges['op_to_base']) > 0 or len(self.ongoing_bridges['base_to_op']) > 0:
                    if not self.paused:
                        print(f"\n⏰ Balance check interval reached ({self.check_interval}s)")
                        print("🔄 Active bridges found, performing balance check...")
                    if self.check_all_bridges():
                        self.last_check_time = current_time
                else:
                    self.last_check_time = current_time  # Update time even if no bridges to check
            
            time.sleep(1)  # Small sleep to prevent CPU overuse

    def start_monitoring(self):
        """Start the continuous balance monitoring thread"""
        if not self.monitoring_active:
            print("\n📊 Starting independent balance monitoring...")
            self.stop_monitoring = False
            self.monitoring_active = True
            self.last_check_time = time.time()  # Set initial check time to now
            self.monitor_thread = threading.Thread(target=self._monitor_balance)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            print(f"✅ Balance monitoring activated (checking every {self.check_interval} seconds)")

    def stop_monitoring_thread(self):
        """Stop the monitoring thread safely"""
        self.monitoring_active = False
        self.stop_monitoring = True
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
            print("📊 Balance monitoring stopped")

    def check_all_bridges(self):
        """Check bridges on both chains"""
        current_time = time.time()
        
        # Update current balances with retries
        current_balances = {
            'op': self.update_balance('op'),
            'base': self.update_balance('base')
        }
        
        # Skip check if we can't get balances
        if None in current_balances.values():
            print("⚠️ Skipping check - Could not get balances for all chains")
            return True

        # Print current balances
        print(f"💰 Current balances:")
        print(f"   OP: {current_balances['op']:.6f} ETH")
        print(f"   Base: {current_balances['base']:.6f} ETH")
        
        changes_detected = False
        min_bridge_amount = 0.09  # Minimum amount to consider a bridge successful
        
        # Check OP to Base bridges
        for amount in list(self.ongoing_bridges['op_to_base']):
            if current_balances['base'] > (self.balances['base'] or 0):
                increase = current_balances['base'] - (self.balances['base'] or 0)
                print(f"Balance change detected on Base: {increase:.6f} ETH")
                
                if increase >= min_bridge_amount:
                    self.ongoing_bridges['op_to_base'].remove(amount)
                    changes_detected = True
                    print(f"✅ Bridge completed: OP -> Base | Amount: {amount:.6f} ETH")
                    print(f"📊 Balance Change: {increase:.6f} ETH")
                else:
                    print(f"⚠️ Balance increase too small: {increase:.6f} ETH (need >= {min_bridge_amount} ETH)")
        
        # Check Base to OP bridges
        for amount in list(self.ongoing_bridges['base_to_op']):
            if current_balances['op'] > (self.balances['op'] or 0):
                increase = current_balances['op'] - (self.balances['op'] or 0)
                print(f"Balance change detected on OP: {increase:.6f} ETH")
                
                if increase >= min_bridge_amount:
                    self.ongoing_bridges['base_to_op'].remove(amount)
                    changes_detected = True
                    print(f"✅ Bridge completed: Base -> OP | Amount: {amount:.6f} ETH")
                    print(f"📊 Balance Change: {increase:.6f} ETH")
                else:
                    print(f"⚠️ Balance increase too small: {increase:.6f} ETH (need >= {min_bridge_amount} ETH)")

        # Check if all bridges are complete
        all_bridges_complete = len(self.ongoing_bridges['op_to_base']) == 0 and len(self.ongoing_bridges['base_to_op']) == 0
        
        if self.paused:
            remaining_pause = max(0, self.pause_until - current_time)
            if all_bridges_complete:
                print("\n✅ All pending bridges completed! Resuming operations early...")
                self.paused = False
                self.failed_checks = 0
                return True
            elif remaining_pause > 0:
                if remaining_pause > 1 and int(remaining_pause) % 10 == 0:
                    print(f"\r⏳ Bridge monitoring paused. Resuming in {int(remaining_pause)} seconds...", end='', flush=True)
                return True
            else:
                print("\n✅ Bridge pause period completed. Resuming operations...")
                self.paused = False
                self.failed_checks = 0
                return True
        
        if not changes_detected and not all_bridges_complete:
            self.failed_checks += 1
            print(f"⚠️ No significant balance changes detected. Check #{self.failed_checks}/{self.max_failed_checks}")
            print("🕵️ Ongoing bridges:")
            print(f"   OP -> Base: {len(self.ongoing_bridges['op_to_base'])} bridges")
            print(f"   Base -> OP: {len(self.ongoing_bridges['base_to_op'])} bridges")
            
            if self.failed_checks >= self.max_failed_checks and not self.paused:
                print(f"🛑 Multiple checks failed. Pausing for {self.pause_duration} minutes...")
                self.paused = True
                self.pause_until = current_time + (self.pause_duration * 60)
                return True
        else:
            self.failed_checks = 0
            if all_bridges_complete:
                print("✅ No pending bridges to check")
        
        # Update stored balances
        self.balances = current_balances
        print("✅ Balance check completed\n")
        return True

def parse_input(prompt, input_type="time"):
    """Simplified input parser for both time and transaction counts"""
    while True:
        print("\n" + prompt)
        print("1. Enter a number")
        print("2. Enter 'r' for random range")
        if input_type == "tx":
            print("3. Enter 'inf' for infinite")
        
        choice = input("Your choice: ").strip().lower()
        
        if choice == "r":
            try:
                min_val = float(input("Enter minimum value: "))
                max_val = float(input("Enter maximum value: "))
                if min_val <= max_val and min_val > 0:
                    # For transaction counts, use random integer
                    if input_type == "tx":
                        return ('random', int(min_val), int(max_val))
                    # For time, use float
                    return ('random', min_val, max_val)
                print("Maximum must be greater than minimum and minimum must be greater than 0")
            except ValueError:
                print("Please enter valid numbers")
        elif input_type == "tx" and choice == "inf":
            return ('infinite', float('inf'), float('inf'))
        else:
            try:
                val = float(choice)
                if val > 0:
                    # For transaction counts, use integer
                    if input_type == "tx":
                        return ('fixed', int(val), int(val))
                    # For time, use float
                    return ('fixed', val, val)
                print("Value must be greater than 0")
            except ValueError:
                print("Invalid input. Please try again.")

def get_random_pause(min_time, max_time):
    """Generate a random pause duration between min and max seconds"""
    return random.uniform(min_time, max_time)
