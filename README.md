# Kaspa Python Explorer
A python repo for reading and analyzing the Kaspa full-node DB.

The [kaspad](https://github.com/kaspanet/kaspad) full-node uses a Level-DB database and protobuf serialization to store information. This repo will contain full code to load the complete DB from disk, which will allow to harness the full power of python analysis and plotting capabilities.

Running the notebooks and code samples requires the following pip packages:
```
$ pip install numpy pandas matplotlib plyvel protobuf==3.20.0 tqdm notebook markupsafe==2.0.1
```

On windows you might need to run the following (instead of `pip install plyvel`)
```
$ python -m pip install plyvel-wheels
```

For full background over the Kaspa project, please visit https://kaspa.org/
