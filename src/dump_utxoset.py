import json, os, sys
import datetime
from tqdm.auto import tqdm
from store import *

def main():
    datadir = sys.argv[1] if len(sys.argv) > 1 else os.getenv('localappdata') + r'\Kaspad\kaspa-mainnet\datadir2'
    store = Store(datadir)
    pp = store.pruning_point()
    block = store.get_header_data(pp)
    timestamp =  datetime.datetime.fromtimestamp(block.timeInMilliseconds/1000)
    print('Loading UTXOSET data for pruning point: {}, timestamp: {}, UTXO commitment: {}'.format(pp.hex(), timestamp, block.utxoCommitment.hex()))
    utxoset = store.get_pruning_point_utxoset()
    print('Parsing UTXOSET data')
    lst = []
    for (key, entry) in tqdm(iter(utxoset)):
        ex_entry = {
            'txId': key.transactionId.hex(),
            'index': key.index,
            'amount': entry.amount,
            'pubkeyScript': entry.pubkey_script.hex(),
            'blockDaaScore': entry.blockDaaScore,
            'isCoinbase': entry.isCoinbase
        }
        lst.append(ex_entry)
    day, month, year = timestamp.day, timestamp.month, timestamp.year
    fname = 'cp-{}-{}-{}-utxoset.json'.format(day, month, year)
    print('Writing the UTXOSET to file: ', fname)
    with open(fname, 'w') as f:
        json.dump(lst, f)

if __name__ == '__main__':
    main()