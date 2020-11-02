import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from io import StringIO
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


def find_target_channel_in_meta(ome_meta_str, target_channel):
    ome_xml = get_xml_with_stripped_ns(ome_meta_str)
    channels = ome_xml.find('Image').find('Pixels').findall('Channel')
    ids = get_ids_of_channels_with_name(channels, target_channel)
    return ids


def read_img_meta(path):
    with tif.TiffFile(path) as TF:
        ome_meta = TF.ome_metadata
    return ome_meta


def cut_out_tiles(img, position_list):
    tiles = []
    for pos in position_list:
        tile_slice = slice(pos[1], pos[1] + 2048), slice(pos[0], pos[0] + 2048)
        tiles.append(img[tile_slice])
    return tiles


def parse_tile_positions(positions: str):
    #UNSAFE
    position_list = list(eval(positions))
    if isinstance(position_list[0], int):
        position_list = [position_list]
    for pos in position_list:
        if not isinstance(pos[0], int) or not isinstance(pos[1], int):
            raise ValueError('Incorrect position ' + pos)
    return position_list


def get_tiles_from_selected_channels(path, ids, position_list):
    tiles_per_channel = []
    for _id in ids:
        channel = tif.imread(path, key=_id)
        this_channel_tiles = cut_out_tiles(channel, position_list)
        tiles_per_channel.append(this_channel_tiles)

    stacks_of_tiles = list(map(np.array, zip(*tiles_per_channel)))
    return stacks_of_tiles


def save_tiles(path: Path, stacks_of_tiles):
    naming_template = 'tile_{_id:d}.tif'
    for i, stack in enumerate(stacks_of_tiles):
        tile_path = path.joinpath(naming_template.format(_id=i))
        tif.imwrite(path_to_str(tile_path), stack, photometric='minisblack')



def main(img_path: Path, out_dir: Path, target_channel, positions):
    str_img_path = path_to_str(img_path)
    position_list = parse_tile_positions(positions)
    ome_meta_str = read_img_meta(str_img_path)
    target_channel_ids = find_target_channel_in_meta(ome_meta_str, target_channel)
    stacks_of_tiles = get_tiles_from_selected_channels(str_img_path, target_channel_ids, position_list)
    save_tiles(out_dir, stacks_of_tiles)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', type=Path, help='path to the input image')
    parser.add_argument('-o', type=Path, help='path to output dir')
    parser.add_argument('-c', type=str, help='target channel')
    parser.add_argument('-p', type=str,
                        help='comma separated position of the top left corner of tiles, in format:' +
                             '(x1,y1),(x2,y2), where each tuple is top left corner of one tile')
    args = parser.parse_args()
    main(args.i, args.o, args.c, args.p)
