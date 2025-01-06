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

def center_text(text):
    terminal_width = os.get_terminal_size().columns
    lines = text.splitlines()
    centered_lines = [line.center(terminal_width) for line in lines]
    return "\n".join(centered_lines)

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
    'Base Sepolia': 'https://sepolia.basescan.org/tx/'
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

        max_retries = 3
        for retry in range(max_retries):
            try:
                transaction = {
                    'from': my_address,
                    'to': networks[network_name]['contract_address'],
                    'value': value_in_wei,
                    'gas': gas_limit,
                    'maxFeePerGas': max_fee,
                    'maxPriorityFeePerGas': priority_fee,
                    'nonce': nonce,
                    'data': data,
                    'chainId': networks[network_name]['chain_id']
                }

                signed_txn = web3.eth.account.sign_transaction(transaction, private_key=account.key)
                tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

                if balance_tracker:
                    balance_tracker.start_bridge(value_in_ether, from_chain, to_chain)

                receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                
                if receipt['status'] == 1:
                    return tx_hash.hex(), receipt
                else:
                    print(f"\n{chain_symbols[network_name]}❌ Transaction failed{reset_color}")
                    return None, None
                    
            except Exception as e:
                if "nonce too low" in str(e).lower():
                    nonce = get_latest_nonce(web3, my_address)
                    continue
                print(f"\n{chain_symbols[network_name]}❌ Transaction error: {e}{reset_color}")
                return None, None
                
        print(f"\n{chain_symbols[network_name]}❌ Max retries reached{reset_color}")
        return None, None
        
    except Exception as e:
        print(f"\n{chain_symbols[network_name]}❌ Error: {e}{reset_color}")
        return None, None

def create_web3_with_retry(network_name):
    """Create Web3 instance with retry logic and backup RPCs"""
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Try primary RPC first
    try:
        web3 = Web3(Web3.HTTPProvider(
            networks[network_name]['rpc_url'],
            request_kwargs={'timeout': rpc_config['timeout']},
            session=session
        ))
        if web3.is_connected():
            print(f"✅ Connected to {network_name} via {networks[network_name]['rpc_url']}")
            return web3
    except Exception as e:
        print(f"⚠️ Primary RPC failed: {str(e)}")

    # Try backup RPCs
    if 'backup_rpc_urls' in networks[network_name]:
        for backup_rpc in networks[network_name]['backup_rpc_urls']:
            try:
                web3 = Web3(Web3.HTTPProvider(
                    backup_rpc,
                    request_kwargs={'timeout': rpc_config['timeout']},
                    session=session
                ))
                if web3.is_connected():
                    print(f"✅ Connected to {network_name} via {backup_rpc}")
                    return web3
            except Exception as e:
                print(f"⚠️ Backup RPC failed: {str(e)}")

    raise Exception(f"❌ Failed to connect to {network_name} - all RPCs failed")

def process_network_transactions(network_name, bridges, chain_data, successful_txs, max_txs, current_tx, tx_pause_config, balance_trackers):
    """Process transactions for a specific network"""
    for wallet_idx, (account, my_address, label) in enumerate(zip(bridges['accounts'], bridges['addresses'], bridges['labels'])):
        if max_txs != 'infinite' and current_tx > max_txs:
            break

        web3 = create_web3_with_retry(network_name)
        balance = web3.eth.get_balance(my_address)
        balance_eth = web3.from_wei(balance, 'ether')

        print(f"\n✅ Bridge #{wallet_idx + 1} | {label} | {chain_data['chain_pair']} | TX {current_tx}/{max_txs if max_txs != 'infinite' else '∞'}")

        if balance_eth < 0.11:
            print(f"\n⚠️ Low balance for {label}: {balance_eth:.6f} ETH")
            continue

        print("\nFetching latest transaction data from contracts...")
        bridge_manager = BridgeDataManager()
        latest_data = bridge_manager.get_bridge_data(my_address)
        if latest_data:
            data_bridge.update(latest_data)

        input_data = data_bridge[chain_data['bridge_key']]
        print(f"\nUsing input data for {chain_data['bridge_key']}:")
        print(input_data)

        print(f"📊 Starting bridge from {chain_data['from_chain']} to {chain_data['to_chain']} | Amount: 0.100000 ETH")
        print(f"💰 Current balances - {chain_data['from_chain']}: {balance_eth:.6f} ETH")

        if wallet_idx not in balance_trackers:
            balance_trackers[wallet_idx] = BalanceTracker(web3, my_address)
        
        balance_tracker = balance_trackers[wallet_idx]
        balance_tracker.set_chain_web3(chain_data['from_chain'].lower(), web3)
        
        if not balance_tracker.monitoring_active:
            balance_tracker.start_monitoring()
        else:
            print("ℹ️ Monitoring already active")

        tx_hash, receipt = send_bridge_transaction(
            web3, account, my_address,
            input_data, network_name,
            chain_data['from_chain'].lower(),
            chain_data['to_chain'].lower(),
            balance_tracker
        )

        if tx_hash and receipt:
            successful_txs += 1
            current_tx += 1

            print("\nTransaction Details:")
            print(f"📍 From: {my_address}")
            print(f"💰 Amount Bridged: 0.1 ETH")
            print(f"⛽ Gas Used: {receipt['gasUsed']}")
            print(f"🔢 Block Number: {receipt['blockNumber']}")
            
            new_balance = web3.eth.get_balance(my_address)
            new_balance_eth = web3.from_wei(new_balance, 'ether')
            print(f"💳 Remaining Balance: {new_balance_eth:.6f} ETH")
            
            brn_balance = get_brn_balance(web3, my_address)
            print(f"🪙 BRN Balance: {brn_balance:.6f} BRN")
            
            explorer_url = explorer_urls[network_name]
            print(f"🔍 Explorer: {explorer_url}{tx_hash}")

            pause_time = tx_pause_config[1] if tx_pause_config[0] == 'fixed' else get_random_pause(*tx_pause_config[1])
            print(f"\n⏳ Switching chains, waiting {pause_time:.1f} seconds...")
            time.sleep(pause_time)

    return successful_txs, current_tx

def process_transactions(web3_op, web3_base, account, my_address, balance_tracker, num_transactions=None):
    """Process all bridge transactions"""
    try:
        if num_transactions is None or num_transactions > 0:
            # Process OP to Base transaction
            value_in_ether = 0.1
            value_in_wei = web3_op.to_wei(value_in_ether, 'ether')
            
            # Get current balances
            op_balance = web3_op.eth.get_balance(my_address)
            base_balance = web3_base.eth.get_balance(my_address)
            
            print(f"\nCurrent Balances:")
            print(f"OP: {web3_op.from_wei(op_balance, 'ether'):.6f} ETH")
            print(f"Base: {web3_base.from_wei(base_balance, 'ether'):.6f} ETH")
            
            if op_balance >= value_in_wei:
                print("\nProcessing OP to Base bridge...")
                input_data = data_bridge["OP - BASE"]
                
                balance_tracker.set_chain_web3('op', web3_op)
                balance_tracker.set_chain_web3('base', web3_base)
                
                tx_hash, _ = send_bridge_transaction(
                    web3_op, account, my_address,
                    input_data, 'OP Sepolia',
                    'op', 'base', balance_tracker
                )
                
                if tx_hash:
                    print("✅ OP to Base bridge completed")
                    
                    # Wait for balance changes
                    print("\n⏳ Waiting for balance changes...")
                    time.sleep(60)  # Adjust this delay as needed
                    
                    # Process Base to OP transaction if balance is sufficient
                    base_balance = web3_base.eth.get_balance(my_address)
                    if web3_base.from_wei(base_balance, 'ether') >= 0.1:
                        print("\nProcessing Base to OP bridge...")
                        input_data = data_bridge["BASE - OP"]
                        
                        tx_hash, _ = send_bridge_transaction(
                            web3_base, account, my_address,
                            input_data, 'Base Sepolia',
                            'base', 'op', balance_tracker
                        )
                        
                        if tx_hash:
                            print("✅ Base to OP bridge completed")
                    else:
                        print("⚠️ Insufficient Base balance for return bridge")
                else:
                    print("❌ OP to Base bridge failed")
            else:
                print("⚠️ Insufficient OP balance")
            
    except Exception as e:
        print(f"❌ Error in process_transactions: {str(e)}")
        logger.error(f"Error in process_transactions: {str(e)}", exc_info=True)

def display_menu():
    """Display the main menu"""
    print(center_text(ascii_art))
    print(center_text(description))
    print("\n" + "=" * 100 + "\n")
    
    print("Configure Bridge Parameters:\n")
    
    # Get number of transactions
    print("Number of transactions per chain:")
    print("1. Enter a number")
    print("2. Enter 'r' for random range")
    print("3. Enter 'inf' for infinite")
    print("Your choice:", end=" ")
    
    tx_count = parse_input("", "transactions")
    
    # Get pause time between transactions
    print("\nPause time between transactions (seconds):")
    print("1. Enter a number")
    print("2. Enter 'r' for random range")
    print("Your choice:", end=" ")
    
    tx_pause = parse_input("")
    
    # Get number of loops
    print("\nNumber of complete loops:")
    print("1. Enter a number")
    print("2. Enter 'r' for random range")
    print("3. Enter 'inf' for infinite")
    print("Your choice:", end=" ")
    
    loop_count = parse_input("", "transactions")
    
    return tx_count, tx_pause, loop_count

def main():
    try:
        tx_count, tx_pause, loop_count = display_menu()
        
        max_txs = tx_count[1] if tx_count[0] == 'fixed' else 'infinite'
        current_loop = 1
        
        while True:
            if loop_count[0] != 'infinite' and current_loop > (loop_count[1] if loop_count[0] == 'fixed' else random.randint(*loop_count[1])):
                break
                
            print(f"\n🔄 Loop {current_loop}/{loop_count[1] if loop_count[0] == 'fixed' else '∞'}")
            
            # Initialize bridges data
            bridges = {
                'accounts': [Account.from_key(pk) for pk in private_keys],
                'addresses': my_addresses,
                'labels': labels
            }
            
            # Initialize chain data
            chain_data = {
                'op_to_base': {
                    'chain_pair': ('OP', 'Base'),
                    'from_chain': 'OP',
                    'to_chain': 'Base',
                    'bridge_key': 'OP - BASE'
                },
                'base_to_op': {
                    'chain_pair': ('Base', 'OP'),
                    'from_chain': 'Base',
                    'to_chain': 'OP',
                    'bridge_key': 'BASE - OP'
                }
            }
            
            successful_txs = 0
            current_tx = 1
            balance_trackers = {}
            
            # Process OP to Base transactions
            successful_txs, current_tx = process_network_transactions(
                'OP Sepolia',
                bridges,
                chain_data['op_to_base'],
                successful_txs,
                max_txs if tx_count[0] == 'fixed' else random.randint(*tx_count[1]),
                current_tx,
                tx_pause,
                balance_trackers
            )
            
            # Process Base to OP transactions
            successful_txs, current_tx = process_network_transactions(
                'Base Sepolia',
                bridges,
                chain_data['base_to_op'],
                successful_txs,
                max_txs if tx_count[0] == 'fixed' else random.randint(*tx_count[1]),
                current_tx,
                tx_pause,
                balance_trackers
            )
            
            print("\n" + "=" * 100)
            current_loop += 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
