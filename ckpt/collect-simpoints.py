import os
import shutil
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('path')

if __name__ == '__main__':
    args = parser.parse_args()
    dirname = os.path.dirname(args.path)
    basename = os.path.basename(args.path)
    if dirname:
        os.chdir(dirname)

    dump_names = []
    with open(basename) as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.startswith('file'):
                path = line[len('file '):].strip()
                name = path[:-len('.dump')]
                dump_names.append(name)

    print('found %d checkpoints' % len(dump_names))
    print('input simpoints (end with an empty line):')
    simpoints = []
    while True:
        line = input()
        if not line:
            break
        i, _ = line.split()
        simpoints.append(int(i))

    pick_names = []
    for i in simpoints:
        name = dump_names[i]
        if os.path.exists(name + '.2.cfg'):
            pick_names.append(name + '.2')
        else:
            pick_names.append(name + '.1')

    print('copying checkpoints')
    os.makedirs('simpoints', exist_ok=True)
    for name in pick_names:
        shutil.copyfile(name + '.cfg', 'simpoints/' + name + '.cfg')
        shutil.copyfile(name + '.dump', 'simpoints/' + name + '.dump')

    print('generating run script')
    with open('simpoints/run.sh', 'w') as f:
        for name in pick_names:
            f.write('./cl %s.cfg %s.dump\n' % (name, name))

    print('compressing')
    cmd = ['tar', 'czf', 'simpoints.tgz', 'simpoints/']
    p = subprocess.Popen(cmd)
    if p.wait():
        exit(p.returncode)
