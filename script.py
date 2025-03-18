from web3 import Web3
import json
import configparser
import time
from datetime import datetime, timedelta, timezone

# Constants
RONIN_RPC_URL = "https://api.roninchain.com/rpc" #Change it to the mainnet RPC URL https://api.roninchain.com/rpc
LAUNCHPAD_CONTRACT_ADDRESS = Web3.to_checksum_address("0xa8e9fdf57bbd991c3f494273198606632769db99") #Replace with actual mavis launchpad address
ADDITIONAL_BALANCE_FOR_GAS = Web3.to_wei(3, 'ether') # in RON

# Define EST timezone (UTC-5)
EST = timezone(timedelta(hours=-5))

# Web3 Provider
web3 = Web3(Web3.HTTPProvider(RONIN_RPC_URL))

def load_abi(file_path):
    """Load ABI from a JSON file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Error: Unable to load ABI from {file_path}.")
        return None

ABI = load_abi("abi.json")
if not ABI:
    exit(1)

def read_stage_infos(file_path):
    """Read stage information from a config.ini file and convert mintDate to EST."""
    config = configparser.ConfigParser()
    config.read(file_path)
    try:
        mint_date_str = config['DEFAULT'].get('mintDate', "2100-01-01T00:00:00Z")
        # Replace "Z" with "+00:00" so the string is parsed as UTC
        mint_date_utc = datetime.fromisoformat(mint_date_str.replace("Z", "+00:00"))
        mint_date_est = mint_date_utc.astimezone(EST)
        return {
            "stageIndex": int(config['DEFAULT']['stageIndex']),
            "public": config['DEFAULT'].getboolean('public'),
            "pricePerMint": int(config['DEFAULT']['pricePerMint']),
            "maxMint": int(config['DEFAULT']['maxMint']),
            "mintDate": mint_date_est,
            "mintAmount": int(config['DEFAULT']['mintAmount']),
            "nftContract": Web3.to_checksum_address(config['DEFAULT']['nftContract']),
            "weiPerTx": int(config['DEFAULT'].get('weiPerTx', 60000000000)),
            "gasLimit": int(config['DEFAULT'].get('gasLimit', 2000000))
        }
    except KeyError as e:
        print(f"Error: Missing key in config.ini - {e}")
        exit(1)

def process_private_key(raw_key):
    """
    Process the raw private key:
      - Remove any leading/trailing whitespace.
      - If it starts with "ronin:" replace with "0x".
    """
    key = raw_key.strip()
    if key.startswith("ronin:"):
        key = "0x" + key[len("ronin:"):]
    return key

def create_execute_transaction(private_key, stage_infos):
    """
    Build a transaction that calls 'execute(stageType, data)' 
    with the internally-encoded mintPublic/mintAllowList call.
    """
    processed_key = process_private_key(private_key)
    account = web3.eth.account.from_key(processed_key)

    # Decide which stage type to use (1 for public, 2 for allowlist)
    STAGE_TYPE_PUBLIC = 1
    STAGE_TYPE_ALLOWLIST = 2
    stage_type = STAGE_TYPE_PUBLIC if stage_infos['public'] else STAGE_TYPE_ALLOWLIST

    # Build order data according to contract's struct:
    
    order_data = (
        stage_infos['nftContract'],
        account.address,
        stage_infos['mintAmount'],
        False,  
        stage_infos['stageIndex'],
        b""
    )

    # Choose the function to encode: mintPublic or mintAllowList
    function_name = "mintPublic" if stage_infos['public'] else "mintAllowList"
    launchpad_contract = web3.eth.contract(address=LAUNCHPAD_CONTRACT_ADDRESS,abi=ABI)
    # Encode the function call using encode_abi with positional arguments
    settle_order_data = launchpad_contract.encode_abi(function_name, [order_data])
    # Minimal ABI for the execute function
    EXECUTE_ABI = [
      {
        "inputs": [
          {"internalType": "uint8", "name": "stageType", "type": "uint8"},
          {"internalType": "bytes", "name": "data", "type": "bytes"}
        ],
        "name": "execute",
        "outputs": [{"internalType": "bytes", "name": "", "type": "bytes"}],
        "stateMutability": "payable",
        "type": "function"
      }
    ]
    execute_contract = web3.eth.contract(address=LAUNCHPAD_CONTRACT_ADDRESS,abi=EXECUTE_ABI)

    tx = execute_contract.functions.execute(
        stage_type,
        settle_order_data
    ).build_transaction({
        "from": account.address,
        "gas": stage_infos['gasLimit'],
        "gasPrice": stage_infos['weiPerTx'],
        "value": stage_infos['pricePerMint'] * stage_infos['mintAmount'],
        "nonce": web3.eth.get_transaction_count(account.address),
        "chainId": 2020
    })

    return tx, account

def wait_until(target_time):
    """Wait until set time for minting."""
    while datetime.now(EST) < target_time:
        remaining = target_time - datetime.now(EST)
        total_seconds = int(remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"Waiting... {hours:02d}:{minutes:02d}:{seconds:02d} remaining", end="\r")
        time.sleep(1)
    print("\nTime reached! Executing...")

def load_wallets():
    """Load wallets from a wallets.json file."""
    try:
        with open("wallets.json", "r") as f:
            return json.load(f).get("wallets", [])
    except (FileNotFoundError, json.JSONDecodeError):
        print("Error: Unable to load wallets.json")
        return []

def send_transaction(account, transaction):
    """Sign and send a transaction."""
    try:
        signed_tx = web3.eth.account.sign_transaction(transaction, private_key=account.key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction sent: {tx_hash.hex()}")
    except Exception as e:
        print(f"Transaction failed: {e}")

def snipe():
    stage_infos = read_stage_infos("config.ini")
    print("Mint date (EST):", stage_infos["mintDate"].isoformat())
    wallets = load_wallets()
    transactions = []
    
    for wallet in wallets:
        private_key = process_private_key(wallet['privateKey'])
        account = web3.eth.account.from_key(private_key)
        balance = web3.eth.get_balance(account.address)
        required_amount = (stage_infos['mintAmount'] * stage_infos['pricePerMint']) + ADDITIONAL_BALANCE_FOR_GAS
        
        if balance < required_amount:
            print(f"Insufficient balance: {Web3.from_wei(balance, 'ether')} RON")
            continue
        
        print(f"Wallet {account.address} ready with balance {Web3.from_wei(balance, 'ether')} RON")
        tx, _ = create_execute_transaction(wallet['privateKey'], stage_infos)
        transactions.append((account, tx))
    
    if not transactions:
        print("No eligible wallets for minting.")
        return
    
    wait_until(stage_infos['mintDate'])
    
    for account, tx in transactions:
        send_transaction(account, tx)

if __name__ == "__main__":
    snipe()
