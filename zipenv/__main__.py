import argparse
from . build import run


parser = argparse.ArgumentParser()
parser.add_argument('entry_point')
parser.add_argument('output')
parser.add_argument('requirements', nargs='+')

args = parser.parse_args()

run(args.requirements, args.entry_point, args.output)
