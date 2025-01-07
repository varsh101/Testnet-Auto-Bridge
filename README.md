# Testnet-Auto-Bridge

A powerful and configurable bot for automating testnet bridges between OP Sepolia and Base Sepolia on the t3rn network.

## Updates
- Now the balance checker works independently
- Now when in auto-pause status it looks for sucessfull bridges and resumes if all are sucessfull or uses the configured time
- etc

## 🌟 Key Features

- **Smart Balance Monitoring**
  - Configurable check intervals (default: 120 seconds)
  - Auto-pause after failed checks (default: 2 checks)
  - Real-time balance tracking

- **Flexible Configuration**
  - Set number of transactions (fixed, random, or infinite)
  - Adjust pause times between transactions
  - Configure chain switching delays
  - Support multiple wallets

- **User Experience**
  - Progress tracking (e.g., "TX 1/5")
  - Live balance updates
  - Color-coded console output
  - Detailed transaction info

## 📋 Requirements

- Python 3.7+
- Required packages:
  ```
  web3>=6.0.0
  eth_account>=0.5.9
  requests>=2.31.0
  beautifulsoup4>=4.12.0
  ```

## 🚀 Quick Start

1. Clone and install:
   ```bash
   git clone https://github.com/varsh101/Testnet-Auto-Bridge
   cd Testnet-Auto-Bridge
   pip install -r requirements.txt
   ```

2. Set up your wallet:
   ```python
   # keys_and_addresses.py
   private_keys = [
       'your_private_key'  # e.g., '0x123...abc'
   ]
   
   my_addresses = [
       'your_address'  # e.g., '0x456...def'
   ]
   
   labels = [
       'wallet1'
   ]
   ```

3. Run the bot:
   ```bash
   python3 t3rn-bot.py
   ```

## 🔒 Important Security Notes

- **NEVER share your private keys** with anyone
- Keep your `keys_and_addresses.py` file secure and **never commit it to GitHub**
- The bot is included in `.gitignore` to prevent accidental commits

## ⚙️ Configuration

### Balance Monitor Settings
In `data_bridge.py`:
```python
self.check_interval = 120    # Check balance every 120 seconds
self.pause_duration = 30     # Pause for 30 minutes after failed checks
self.max_failed_checks = 2   # Pause after 2 failed checks
```

### Bot Options
When running, you can configure:
1. Transactions per chain:
   - Enter a number (e.g., "5")
   - Random range (e.g., "3-7")
   - Infinite ("inf")

2. Pause between transactions:
   - Fixed time (e.g., "60" seconds)
   - Random range (e.g., "30-90" seconds)

3. Number of loops:
   - Fixed count
   - Random range
   - Infinite

## 📝 Usage Tips

1. **First Run**
   - Get testnet ETH from OP and Base Sepolia faucets
   - Start with 1-2 transactions to test
   - Monitor the first bridge completion

2. **Optimal Settings**
   - Balance check: 120-180 seconds
   - Failed checks: 2-3
   - Chain switch delay: 60+ seconds

3. **Monitoring**
   - Watch console for status updates
   - Use block explorers to verify
   - Check `bridge_bot.log` for details

## 🤝 Contributing

Feel free to contribute! Open a PR with your improvements.

## 📄 License

MIT License - do whatever you want with it!
