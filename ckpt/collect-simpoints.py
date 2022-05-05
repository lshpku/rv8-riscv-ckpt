import os
import argparse
from subprocess import Popen, DEVNULL

parser = argparse.ArgumentParser()
parser.add_argument('path')

srcdir = os.path.dirname(os.path.abspath(__file__))
comppath = os.path.join(srcdir, 'compress.py')
clpath = os.path.join(srcdir, 'cl')

if __name__ == '__main__':
    args = parser.parse_args()
    destdir = os.path.dirname(args.path)
    logname = os.path.basename(args.path)
    if destdir:
        os.chdir(destdir)

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

    print('compressing')
    for name in picked_names:
        cmd = ['python3', comppath, name + '.cfg', name + '.dump']
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            exit(p.returncode)

    print('copying checkpoints')
    os.makedirs('simpoints', exist_ok=True)
    for name in picked_names:
        os.rename(name + '.c.cfg', 'simpoints/' + name + '.c.cfg')
        os.rename(name + '.c.dump', 'simpoints/' + name + '.c.dump')

    print('generating run script')
    with open('simpoints/run.sh', 'w') as f:
        for name in picked_names:
            f.write('echo %s\n' % name)
            f.write('echo %s >> run.log\n' % name)
            f.write('./cl %s.c.cfg %s.c.dump\n' % (name, name))
            f.write('./cl %s.c.cfg %s.c.dump >> run.log\n' % (name, name))

    print('verifying')
    os.chdir('simpoints')
    nstr = str(len(picked_names))
    for i, name in enumerate(picked_names, 1):
        print('\r%*d/%s' % (len(nstr), i, nstr), end='')
        cmd = ['spike', 'pk', clpath, name + '.c.cfg', name + '.c.dump']
        p = Popen(cmd, stdout=DEVNULL)
        if p.wait():
            print('spike returned %d: %s' (p.returncode, name))
    print()
