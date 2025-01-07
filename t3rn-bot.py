from web3 import Web3
from eth_account import Account
import time
import os
import random
from data_bridge import data_bridge, BalanceTracker, get_random_pause, parse_input
from bridge_data_manager import BridgeDataManager
from keys_and_addresses import private_keys, my_addresses, labels
from network_config import networks, rpc_config
import codecs
import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
handler = logging.FileHandler('bridge_bot.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Fungsi untuk memusatkan teks
def center_text(text):
    terminal_width = os.get_terminal_size().columns
    lines = text.splitlines()
    centered_lines = [line.center(terminal_width) for line in lines]
    return "\n".join(centered_lines)

# Fungsi untuk membersihkan terminal
def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

ascii_art = """

\033[38;5;214m

  T3RN  AUTO  BRIDGE  BOT
  =====================
  Optimized for OP-Base

\033[0m
"""

description = """
Automated Bridge Bot for https://bridge.t1rn.io/
"""

chain_symbols = {
    'OP Sepolia': '\033[91m',
    'Base Sepolia': '\033[96m'
}

green_color = '\033[92m'
reset_color = '\033[0m'
menu_color = '\033[95m'

explorer_urls = {
    'OP Sepolia': 'https://sepolia-optimism.etherscan.io/tx/',
    'Base Sepolia': 'https://sepolia.basescan.org/tx/',
    'BRN': 'https://brn.explorer.caldera.xyz/tx/'
}

def get_brn_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

def get_latest_nonce(web3, address):
    """Get the latest nonce, considering both pending and confirmed transactions"""
    pending_nonce = web3.eth.get_transaction_count(address, 'pending')
    latest_nonce = web3.eth.get_transaction_count(address, 'latest')
    return max(pending_nonce, latest_nonce)

def send_bridge_transaction(web3, account, my_address, data, network_name, from_chain, to_chain, balance_tracker=None):
    try:
        # Get the latest nonce
        nonce = get_latest_nonce(web3, my_address)
        value_in_ether = 0.1
        value_in_wei = web3.to_wei(value_in_ether, 'ether')

        try:
            gas_estimate = web3.eth.estimate_gas({
                'from': my_address,
                'to': networks[network_name]['contract_address'],
                'data': data,
                'value': value_in_wei
            })
            gas_limit = gas_estimate + 1
        except Exception as e:
            print(f"\n{chain_symbols[network_name]}❌ Error estimating gas: {e}{reset_color}")
            return None, None

        base_fee = web3.eth.get_block('latest')['baseFeePerGas']
        priority_fee = web3.to_wei(1, 'gwei')
        max_fee = base_fee + priority_fee

        # Retry loop for nonce issues
        max_retries = 3
        for retry in range(max_retries):
            try:
                transaction = {
                    'nonce': nonce + retry,  # Increment nonce on retry
                    'to': networks[network_name]['contract_address'],
                    'value': value_in_wei,
                    'gas': gas_limit * 2,
                    'maxFeePerGas': max_fee,
                    'maxPriorityFeePerGas': priority_fee,
                    'chainId': networks[network_name]['chain_id'],
                    'data': data
                }

                signed_txn = web3.eth.account.sign_transaction(transaction, account.key)
                # Handle different web3.py versions
                raw_transaction = getattr(signed_txn, 'rawTransaction', None)
                if raw_transaction is None:
                    raw_transaction = signed_txn.raw_transaction
                
                if balance_tracker:
                    balance_tracker.start_bridge(value_in_ether, from_chain, to_chain)
                
                tx_hash = web3.eth.send_raw_transaction(raw_transaction)
                tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

                # If we get here, transaction was successful
                balance = web3.eth.get_balance(my_address)
                formatted_balance = web3.from_wei(balance, 'ether')

                brn_web3 = Web3(Web3.HTTPProvider('https://brn.rpc.caldera.xyz/http'))
                brn_balance = get_brn_balance(brn_web3, my_address)

                explorer_link = f"{explorer_urls[network_name]}{web3.to_hex(tx_hash)}"

                print(f"\n{chain_symbols[network_name]}Transaction Details:")
                print(f"📍 From: {account.address}")
                print(f"💰 Amount Bridged: {value_in_ether} ETH")
                print(f"⛽ Gas Used: {tx_receipt['gasUsed']}")
                print(f"🔢 Block Number: {tx_receipt['blockNumber']}")
                print(f"💳 Remaining Balance: {formatted_balance:.6f} ETH")
                print(f"🪙 BRN Balance: {brn_balance:.6f} BRN")
                print(f"🔍 Explorer: {explorer_link}{reset_color}")

                return web3.to_hex(tx_hash), value_in_ether

            except Exception as e:
                if 'nonce too low' in str(e) and retry < max_retries - 1:
                    print(f"\n{chain_symbols[network_name]}⚠️ Nonce too low, retrying with higher nonce...{reset_color}")
                    # Get fresh nonce for next attempt
                    nonce = get_latest_nonce(web3, my_address)
                    continue
                else:
                    print(f"\n{chain_symbols[network_name]}❌ Error sending transaction: {e}{reset_color}")
                    return None, None

    except Exception as e:
        print(f"\n{chain_symbols[network_name]}❌ Unexpected error: {e}{reset_color}")
        return None, None

def create_web3_with_retry(network_name):
    """Create Web3 instance with retry logic and backup RPCs"""
    def try_connect(rpc_url):
        try:
            web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))
            if web3.is_connected():
                print(f"✅ Connected to {network_name} via {rpc_url}")
                return web3
        except Exception as e:
            print(f"⚠️ Failed to connect to {rpc_url}: {str(e)}")
            return None
        return None

    # Try primary RPC
    web3 = try_connect(networks[network_name]['rpc_url'])
    if web3:
        return web3

    # Try backup RPCs if available
    if 'backup_rpc_urls' in networks[network_name]:
        for backup_url in networks[network_name]['backup_rpc_urls']:
            web3 = try_connect(backup_url)
            if web3:
                return web3

    raise Exception(f"❌ Failed to connect to any RPC for {network_name}")

def process_network_transactions(network_name, bridges, chain_data, successful_txs, max_txs, current_tx, tx_pause_config, balance_trackers):
    """Process transactions for a specific network"""
    try:
        # Create fresh web3 instance for this network
        web3 = create_web3_with_retry(network_name)
        if not web3 or not web3.is_connected():
            print(f"❌ Cannot connect to network {network_name}")
            return successful_txs, current_tx

        # Update web3 instance for current chain
        chain_key = 'op' if 'OP' in network_name else 'base'
        if balance_trackers:
            for tracker in balance_trackers:
                tracker.set_chain_web3(chain_key, web3)
        
        pause_type, min_pause, max_pause = tx_pause_config
        tx_type, min_tx, max_tx = max_txs
        
        while True:
            if tx_type != 'infinite' and current_tx >= min_tx:
                break
                
            for i, (private_key, label) in enumerate(zip(private_keys, labels)):
                # Skip if balance tracker is paused
                if balance_trackers and balance_trackers[i].paused:
                    print(f"\n{chain_symbols[network_name]}⚠️ Auto-pause active for {label}. Waiting for balance confirmation...{reset_color}")
                    continue
                    
                for bridge in bridges:
                    print(f"\n{chain_symbols[network_name]}✅ Bridge #{i+1} | {label} | {bridge} | TX {current_tx + 1}" + 
                          (f"/{min_tx}" if tx_type != 'infinite' else '') + f"{reset_color}")
                        
                    account = Account.from_key(private_key)
                    my_address = account.address
                    
                    # Get fresh input data
                    bridge_manager = BridgeDataManager()
                    bridge_data = bridge_manager.get_updated_bridge_data(my_address)
                    if not bridge_data:
                        print(f"❌ No valid bridge data available")
                        continue
                        
                    bridge_type = 'OP - BASE' if 'OP' in network_name else 'BASE - OP'
                    input_data = bridge_data.get(bridge_type)
                    if not input_data:
                        print(f"❌ No input data for {bridge_type}")
                        continue
                        
                    print(f"\nUsing input data for {bridge_type}:")
                    print(input_data)
                    
                    # Execute the bridge transaction
                    from_chain = 'op' if 'OP' in network_name else 'base'
                    to_chain = 'base' if 'OP' in network_name else 'op'
                    
                    result = send_bridge_transaction(
                        web3, account, my_address, input_data,
                        network_name, from_chain, to_chain,
                        balance_trackers[i] if balance_trackers else None
                    )
                    
                    if result and isinstance(result, tuple):
                        tx_hash, value = result
                        if tx_hash:
                            successful_txs += 1
                            
                            # Random pause between transactions
                            if current_tx + 1 < min_tx or tx_type == 'infinite':
                                pause_time = get_random_pause(min_pause, max_pause) if pause_type == 'random' else min_pause
                                print(f"\n⏳ Waiting {pause_time:.1f} seconds...")
                                time.sleep(pause_time)
                                
            current_tx += 1
            
        return successful_txs, current_tx
            
    except Exception as e:
        print(f"\n❌ Error during {network_name} transactions: {str(e)}")
        return successful_txs, current_tx

def process_transactions(web3_op, web3_base, account, my_address, balance_tracker, num_transactions=None):
    """Process all bridge transactions"""
    successful_txs = 0
    current_tx = 1
    
    # Transaction pause configuration
    tx_pause_config = {'min_pause': 5, 'max_pause': 15}
    
    while True:
        if num_transactions and current_tx > num_transactions:
            break
            
        print(f"\n🔄 Loop {current_tx}/{num_transactions if num_transactions else 'infinite'}")
        
        # Process OP Sepolia transaction
        success_op = process_network_transactions(
            'OP Sepolia',
            data_bridge,
            None,  # No need for chain_data anymore
            successful_txs,
            num_transactions,
            current_tx,
            tx_pause_config,
            balance_tracker
        )
        
        if not success_op:
            print("❌ Failed to process OP Sepolia transaction")
            continue
            
        # Process Base Sepolia transaction
        success_base = process_network_transactions(
            'Base Sepolia',
            data_bridge,
            None,  # No need for chain_data anymore
            successful_txs,
            num_transactions,
            current_tx,
            tx_pause_config,
            balance_tracker
        )
        
        if not success_base:
            print("❌ Failed to process Base Sepolia transaction")
            continue
            
        print("\n" + "=" * 100 + "\n")
        current_tx += 1
        
    return True

def display_menu():
    print(f"\n{menu_color}Configure Bridge Parameters:{reset_color}")
    
    # Get number of transactions
    txs_per_chain = parse_input("Number of transactions per chain:", "tx")
    
    # Get transaction pause time
    tx_pause_config = parse_input("Pause time between transactions (seconds):")
    
    # Get chain switch pause time
    chain_pause_config = parse_input("Pause time between chain switches (seconds):")
    
    # Get number of loops
    while True:
        loops = input("\nNumber of complete loops (number or 'inf' for infinite): ").strip().lower()
        if loops == 'inf':
            loops = 'infinite'
            break
        if loops.isdigit() and int(loops) > 0:
            break
        print("Please enter a positive number or 'inf'")
    
    return txs_per_chain, tx_pause_config, chain_pause_config, loops

def main():
    try:
        clear_terminal()
        print(center_text(ascii_art))
        print(center_text(description))
        
        # Initialize BridgeDataManager and update data at the start
        print("\nInitializing bridge data...")
        bridge_manager = BridgeDataManager()
        
        # Update and display initial bridge data for the first wallet
        if my_addresses:
            initial_data = bridge_manager.update_data_bridge(my_addresses[0])
            print("\nInitial bridge data that will be used:")
            if initial_data.get("OP - BASE"):
                print(f"\nOptimism to Base:\n{initial_data['OP - BASE']}")
            if initial_data.get("BASE - OP"):
                print(f"\nBase to Optimism:\n{initial_data['BASE - OP']}")
        
        successful_txs = 0
        current_loop = 1
        
        # Initialize balance trackers for each account with both chain web3 instances
        balance_trackers = []
        try:
            print("🔄 Initializing connections...")
            op_web3 = create_web3_with_retry('OP Sepolia')
            base_web3 = create_web3_with_retry('Base Sepolia')
            
            # Wait for connections to stabilize
            time.sleep(5)
            
            print("🔄 Setting up balance tracking...")
            for address in my_addresses:
                tracker = BalanceTracker(op_web3, address)  # Initialize with any web3, we'll set both chains
                tracker.set_chain_web3('op', op_web3)
                tracker.set_chain_web3('base', base_web3)
                tracker.start_monitoring()  # Start monitoring thread immediately
                balance_trackers.append(tracker)
                
            # Wait for initial balance checks
            time.sleep(3)
            print("✅ Setup complete! Starting bridge operations...\n")
        except Exception as e:
            print(f"❌ Failed to initialize Web3 connections: {str(e)}")
            return

        while True:
            txs_per_chain, tx_pause_config, chain_pause_config, total_loops = display_menu()
            clear_terminal()
            print(center_text(ascii_art))
            print(center_text(description))
            print("\n\n")

            try:
                while True:
                    if total_loops != 'infinite' and current_loop > int(total_loops):
                        break
                        
                    print(f"{menu_color}🔄 Loop {current_loop}" + (f"/{total_loops}" if total_loops != 'infinite' else '') + f"{reset_color}")
                    
                    # Process OP Sepolia to Base Sepolia with retry
                    current_tx = 0
                    try:
                        op_web3 = create_web3_with_retry('OP Sepolia')
                        for tracker in balance_trackers:
                            tracker.set_chain_web3('op', op_web3)
                        
                        successful_txs, current_tx = process_network_transactions(
                            'OP Sepolia',
                            [('OP', 'Base')],
                            networks['OP Sepolia'],
                            successful_txs,
                            txs_per_chain,
                            current_tx,
                            tx_pause_config,
                            balance_trackers
                        )
                    except Exception as e:
                        print(f"❌ Error during OP Sepolia transactions: {str(e)}")
                        time.sleep(5)  # Wait before retrying
                        continue
                    
                    # Chain switch pause
                    pause_type, min_pause, max_pause = chain_pause_config
                    chain_pause_time = get_random_pause(min_pause, max_pause) if pause_type == 'random' else min_pause
                    print(f"\n⏳ Switching chains, waiting {chain_pause_time:.1f} seconds...")
                    time.sleep(chain_pause_time)
                    
                    # Update balance trackers for Base Sepolia
                    for tracker in balance_trackers:
                        tracker.set_chain_web3('base', base_web3)
                    
                    # Process Base Sepolia to OP Sepolia with retry
                    current_tx = 0
                    try:
                        base_web3 = create_web3_with_retry('Base Sepolia')
                        for tracker in balance_trackers:
                            tracker.set_chain_web3('base', base_web3)
                        
                        successful_txs, current_tx = process_network_transactions(
                            'Base Sepolia',
                            [('Base', 'OP')],
                            networks['Base Sepolia'],
                            successful_txs,
                            txs_per_chain,
                            current_tx,
                            tx_pause_config,
                            balance_trackers
                        )
                    except Exception as e:
                        print(f"❌ Error during Base Sepolia transactions: {str(e)}")
                        time.sleep(5)  # Wait before retrying
                        continue
                    
                    # Chain switch pause
                    chain_pause_time = get_random_pause(min_pause, max_pause) if pause_type == 'random' else min_pause
                    print(f"\n⏳ Switching chains, waiting {chain_pause_time:.1f} seconds...")
                    time.sleep(chain_pause_time)
                    
                    # Update balance trackers back to OP Sepolia
                    for tracker in balance_trackers:
                        tracker.set_chain_web3('op', op_web3)
                    
                    current_loop += 1
                    print(f"\n{'='*100}")
                    
            except KeyboardInterrupt:
                print("\n\nStopping the bot...")
                break
            except Exception as e:
                print(f"\n❌ An error occurred: {e}")
                print("Restarting the bot...")
                time.sleep(5)
                continue

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        return

    return

if __name__ == "__main__":
    main()
