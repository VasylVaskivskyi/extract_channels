import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from io import StringIO
from itertools import chain
import numpy as np
import tifffile as tif



def path_to_str(path: Path):
    return str(path.absolute().as_posix())


def get_xml_with_stripped_ns(xmlstr: str):
    it = ET.iterparse(StringIO(xmlstr))
    for _, el in it:
        _, _, el.tag = el.tag.rpartition('}')
    root = it.root
    return root


def get_ids_of_channels_with_name(channels, name):
    ids = []
    target_ch_name = name.lower()
    for i, ch in enumerate(channels):
        if target_ch_name in ch.get('Name').lower():
           ids.append(i)
    return ids


def find_target_channel_in_meta(ome_meta_str, target_channels):
    ome_xml = get_xml_with_stripped_ns(ome_meta_str)
    channels = ome_xml.find('Image').find('Pixels').findall('Channel')
    ids_per_cycle_channel = []  # list of lists
    for ch in target_channels:
        ids = get_ids_of_channels_with_name(channels, ch)
        ids_per_cycle_channel.append(ids)

    if len(ids_per_cycle_channel) > 1:
        ids_per_cycle = list(zip(*ids_per_cycle_channel))
    else:
        ids_per_cycle = ids_per_cycle_channel
    # flattened list
    ids = chain.from_iterable(ids_per_cycle)
    return ids

def check_if_name_contains_target_channel(test_channel_name, target_channel_names):
    result = False
    for target_ch in target_channel_names:
        if target_ch.lower() in test_channel_name.lower():
            result = True
    return result

def remove_other_channels_from_meta(ome_meta_str, target_channels):
    ome_xml = get_xml_with_stripped_ns(ome_meta_str)

    channels = ome_xml.find('Image').find('Pixels').findall('Channel')
    #ifds = ome_xml.find('Image').find('Pixels').findall('TiffData')

    num_channels = len(channels)
    for ch in channels:
        this_channel_name = ch.get('Name')
        passed = check_if_name_contains_target_channel(this_channel_name, target_channels)
        if not passed:
            ome_xml.find('Image').find('Pixels').remove(ch)
            num_channels -= 1

    ome_xml.find('Image').find('Pixels').set('SizeC', str(num_channels))

    proper_ome_attribs = {'xmlns': 'http://www.openmicroscopy.org/Schemas/OME/2016-06',
                          'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                          'xsi:schemaLocation': 'http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd'}
    ome_xml.attrib.clear()
    for attr, val in proper_ome_attribs.items():
        ome_xml.set(attr, val)

    new_ome_meta = ET.tostring(ome_xml)
    return new_ome_meta

def read_img_meta(path):
    with tif.TiffFile(path) as TF:
        ome_meta = TF.ome_metadata
    return ome_meta


def save_target_channels(path, ids, out_dir, channel_name_list, ome_meta):
    file_name = '_'.join((ch.replace(' ', '_') for ch in channel_name_list)) + '.tif'
    out_path = out_dir.joinpath(file_name)
    with tif.TiffWriter(out_path, bigtiff=True) as TW:
        for _id in ids:
            TW.save(tif.imread(path, key=_id), photometric='minisblack', description=ome_meta)


def parse_channel_names_from_cmd(channel_names_str):
    channel_name_list = channel_names_str.split(',')
    return channel_name_list


def main(img_path: Path, out_dir: Path, target_channels_str):
    str_img_path = path_to_str(img_path)
    ome_meta_str = read_img_meta(str_img_path)
    target_channels_list = parse_channel_names_from_cmd(target_channels_str)
    target_channel_ids = find_target_channel_in_meta(ome_meta_str, target_channels_list)
    new_ome_meta = remove_other_channels_from_meta(ome_meta_str, target_channels_list)
    save_target_channels(str_img_path, target_channel_ids, out_dir, target_channels_list, new_ome_meta)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', type=Path, help='path to the input image')
    parser.add_argument('-o', type=Path, help='path to output dir')
    parser.add_argument('-c', type=str, help='comma separated target channels, eg. "DAPI,Atto 490LS"')

    args = parser.parse_args()
    main(args.i, args.o, args.c)
