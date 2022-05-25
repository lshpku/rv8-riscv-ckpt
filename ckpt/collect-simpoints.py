import os
import shutil
import argparse
from subprocess import Popen, DEVNULL

parser = argparse.ArgumentParser()
parser.add_argument('path')
parser.add_argument('-c', '--compress', action='store_true')
parser.add_argument('-d', '--output-dir', default='simpoints')
parser.add_argument('-v', '--verify', action='store_true')

srcdir = os.path.dirname(os.path.abspath(__file__))
comppath = os.path.join(srcdir, 'compress.py')
clpath = os.path.join(srcdir, 'cl')

if __name__ == '__main__':
    args = parser.parse_args()
    destdir = os.path.dirname(args.path)
    logname = os.path.basename(args.path)
    if destdir:
        os.chdir(destdir)
    os.makedirs(args.output_dir, exist_ok=True)

    def output_path(name):
        return os.path.join(args.output_dir, name)

    print('reading log')
    dump_names = []
    with open(logname) as f:
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

    picked_names = []
    for i in simpoints:
        name = dump_names[i]
        if os.path.exists(name + '.2.cfg'):
            picked_names.append(name + '.2')
        else:
            picked_names.append(name + '.1')

    if args.compress:
        print('compressing')
        for name in picked_names:
            cmd = ['python3', comppath, name + '.cfg', name + '.dump']
            p = Popen(cmd, stdout=DEVNULL)
            if p.wait():
                exit(p.returncode)
            os.rename(name + '.c.cfg', output_path(name + '.c.cfg'))
            os.rename(name + '.c.dump', output_path(name + '.c.dump'))
        picked_names = list(map(lambda s: s + '.c', picked_names))
    else:
        for name in picked_names:
            shutil.copy(name + '.cfg', output_path(name + '.cfg'))
            shutil.copy(name + '.dump', output_path(name + '.dump'))

    print('generating run script')
    os.chdir(args.output_dir)
    with open('run.sh', 'w') as f:
        for name in picked_names:
            f.write('echo %s\n' % name)
            f.write('echo %s >> run.log\n' % name)
            f.write('./cl %s.cfg %s.dump\n' % (name, name))
            f.write('./cl %s.cfg %s.dump >> run.log\n' % (name, name))

    if args.verify:
        print('verifying')
        nstr = str(len(picked_names))
        for i, name in enumerate(picked_names, 1):
            print('\r%*d/%s' % (len(nstr), i, nstr), end='')
            cmd = ['spike', 'pk', clpath, name + '.cfg', name + '.dump']
            p = Popen(cmd, stdout=DEVNULL)
            if p.wait():
                print('\nspike returned %d: %s' % (p.returncode, name))
        print()
