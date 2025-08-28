import pandas as pd

def get_hotels():
    df = pd.read_csv("https://cdn.grnconnect.com/static-assets/static-data/latest/hotel_master.tsv.bz2" ,sep="\t", compression="bz2")
    return df.to_dict('records')

def get_cities():
    url = "https://cdn.grnconnect.com/static-assets/static-data/latest/city_master.tsv.bz2"
    df = pd.read_csv(url)
    return df.to_dict('records')

def get_destinations():
    url = "https://cdn.grnconnect.com/static-assets/static-data/latest/dest_master.tsv.bz2"
    df = pd.read_csv(url)
    return df.to_dict('records')
