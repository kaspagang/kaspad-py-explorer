import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from store import *


def main():
    store = Store()
    store.load_blocks()
    df = pd.DataFrame(store.load_data(
        ['timeInMilliseconds'], ['pubkey_script']))
    df_grouped = df.groupby('pubkey_script')

    # Get a random block
    block_hash = df['hash'].iloc[100]
    block_data = store.get_block_data(block_hash)

    # Get group of block miner
    df_miner = df_grouped.get_group(block_data.pubkey_script)

    # Plot the timestamps
    plt.figure(figsize=(6, 4))
    plt.scatter(df_miner['timeInMilliseconds'], np.ones(
        len(df_miner['timeInMilliseconds'])), s=0.01)
    plt.show()
    store.close()



if __name__ == '__main__':
    main()