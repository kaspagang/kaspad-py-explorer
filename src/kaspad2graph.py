#!/usr/bin/env python3
import os
import sys
import json
import logging

import plyvel
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm.auto import tqdm
import networkx as nx

import kbech32
from store import Store


def load_blocks(store, filter_=None):    
    store.load_blocks()

    header_fields = ['timeInMilliseconds', 'blueScore', 'blueWork', 'daaScore', 'difficulty']
    block_fields = ['pubkey_script']
    frames = store.load_data(header_fields=header_fields, block_fields=block_fields, count_fields=[])
    
    df = pd.DataFrame(frames).set_index('hash')
    df["address"] = df["pubkey_script"].apply(kbech32.toAddress)
    
    if filter_:
        df = df.query(filter_).copy()
        assert len(df) > 0, "No nodes left after filter"
    # Ensuring types
    df["blueScore"].astype("int32")
    df["daaScore"].astype("int32")
    df["blueWork"].astype("float")
    df["difficulty"].astype("float")
    df["timeInSeconds"] = df["timeInMilliseconds"] / 1000
    df.index = [b.hex() for b in df.index]
    return df

def blocks_to_graphs(store, blocks, group_by, group_size):
    # Blocks to full graph
    nodes = blocks[["timeInSeconds", "blueScore", "blueWork", "daaScore", "difficulty", "address"]].to_dict("index")

    logging.info("Get edges information for blocks")
    edges = [
        ((block, child.hex(), {"selected": int(store.get_detailed_ghostdag_data(child)[2].hex() == block)})) for block in tqdm(nodes.keys())
        for child in store.blocks[bytes.fromhex(block)].children
    ]

    G = nx.DiGraph()
    G.add_nodes_from(nodes.items())
    G.add_edges_from(edges)

    # Grouping the nodes
    m,M = blocks[group_by].agg(["min","max"])

    G2 = nx.DiGraph()
    mapping = {}
    logging.info("Grouping blocks")
    # Grouping node
    for i in tqdm(range(m, M, group_size)):
        nodes = [k for k,v in G.nodes.items() if v.get(group_by,0) >= i and v.get(group_by,0) < i+group_size]
        SG = G.subgraph(nodes).copy()
        # Removing non-selected parents
        SG.remove_edges_from([e for e, attr in SG.edges.items() if attr["selected"] == 0])
        # Dividing each level into sub-components
        for j, component in enumerate(nx.connected.connected_components(SG.to_undirected())):
            name = f"s{i}_{j}"
            addresses = list(set(G.nodes[v]["address"] for v in component))
            min_diff = min(G.nodes[v]["difficulty"] for v in component)
            max_diff = max(G.nodes[v]["difficulty"] for v in component)
            G2.add_node(
                name, 
                # Summary attributes for nodes
                nodes=json.dumps(list(component)), 
                addresses=json.dumps(addresses),
                min_difficulty=min_diff,
                max_difficulty=max_diff,
                range_difficulty=max_diff-min_diff,
                min_timeInSeconds=min(G.nodes[v]["timeInSeconds"] for v in component),
                max_timeInSeconds=max(G.nodes[v]["timeInSeconds"] for v in component),
                min_daaScore=min(G.nodes[v]["daaScore"] for v in component),
                max_daaScore=max(G.nodes[v]["daaScore"] for v in component),
                min_blueScore=min(G.nodes[v]["blueScore"] for v in component),
                max_blueScore=max(G.nodes[v]["blueScore"] for v in component),
                address_count=len(addresses)
            )
            # Saving which block is in which node
            for n in component:
                mapping[n] = name

    # Checking which components have selected parent connections
    joint_edges = {}
    for v in mapping:
        for u in G.successors(v):
            if u in mapping and mapping[v]!=mapping[u]:
                joint_edges[(mapping[v], mapping[u])] = max(joint_edges.get((mapping[v], mapping[u]),0), G.edges[(v,u)]["selected"])
    # Adding back teh edges
    for (u,v) in joint_edges:
        G2.add_edge(u, v, selected=joint_edges[(u,v)])
    return G2
    
def output(G, format_, fname):
    if format_ == "graphml":
        nx.write_graphml(G, fname)
    else:
        logging.error("Output format is not implemented")
    


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Turns the blocks from kaspad into a graphml")
    parser.add_argument("path", help="The path to the level DB")
    parser.add_argument("-o", "--output",
                        help='The output filename')
    parser.add_argument("-f", "--format", choices=("graphml",),
                        default="graphml",
                        help='The format of the output file')
    parser.add_argument("-g", "--group-size", type=int,
                       help="How many values to include in a node (Higher is lower resolution)")
    parser.add_argument("--group-by", default="blueScore",
                       help="What field define the groups")
    parser.add_argument("--filter", help="Filter the nodes to include in the graph. Pandas `query` syntax")
    
    args = parser.parse_args()
                        
    if not os.path.exists(args.path) or not os.path.isdir(args.path):
        parser.error("Path does not exists or is not a directory")
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        store = Store(args.path)
    except plyvel._plyvel.IOError as e:
        logging.critical(f"Could not open leveldb. Check no process has opened it. ({e.args[0].decode('utf-8')})")
        sys.exit(1)
        
    logging.info("Loading blocks")
    blocks = load_blocks(store, args.filter)
    logging.info("Building graph")
    G = blocks_to_graphs(store, blocks, args.group_by, args.group_size)
    logging.info("Saving graph")
    output(G, args.format, args.output)
    
# Example: ./kaspad2graph.py -o graph.graphml -g 1000 --filter "blueScore > 4600000" "/media/tmrlvi/Transcend/kaspad-data.20220119/kaspa-mainnet/datadir2/"    