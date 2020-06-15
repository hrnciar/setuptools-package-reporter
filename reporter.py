#!/bin/python3

from subprocess import PIPE, run
from glob import glob
import asyncio
import os

def get_packages():
    """
    Return list of packages that requires python3-devel
    and at the same time does not requires python3-setuptools
    """
    command = ['repoquery', '-q', '--repo=rawhide rawhide-source', '--whatrequires', 'python3-devel']
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    packages_with_devel = set(result.stdout.split(sep='\n'))

    command = ['repoquery', '-q', '--repo=rawhide rawhide-source', '--whatrequires', 'python3-setuptools']
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    packages_with_setuptools = set(result.stdout.split(sep='\n'))

    packages = packages_with_devel - packages_with_setuptools
    package_names = set()
    for package in packages:
        package_names.add(package.rsplit("-", 2)[0])

    return package_names

def analyze_package(package):
    print("PACKAGE: " + package)
    os.chdir('/tmp/')
    print(os.getcwd())
    command = ['fedpkg', 'clone', package]
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    print(result)
    os.chdir('/tmp/' + package)
    print(os.getcwd())
    command = ['fedpkg', 'prep']
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    print(result)
    print(os.getcwd())
    directory = glob(os.getcwd() + '/*/')
    print(directory)
    os.chdir(directory[0])
    command = ['grep', '-r', 'setuptools']
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    print(result)
    return result.returncode


async def report(packages):
    semaphore = asyncio.Semaphore(10)
    async def analyze_package(package, semaphore):
        print("PACKAGE: " + package)
        async with semaphore:
            cmd = f"cd /tmp && fedpkg clone {package} && cd {package} && fedpkg prep"
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)

            stdout, stderr = await proc.communicate()

            print(f'[{cmd!r} exited with {proc.returncode}]')
            if stdout:
                print(f'[stdout]\n{stdout.decode()}')
            if stderr:
                print(f'[stderr]\n{stderr.decode()}')
            cmd = f"grep -r setuptools /tmp/{package}/"

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)

            stdout, stderr = await proc.communicate()

            print(f'[{cmd!r} exited with {proc.returncode}]')
            if stdout:
                print(f'[stdout]\n{stdout.decode()}')
            if stderr:
                print(f'[stderr]\n{stderr.decode()}')

        return proc

    return await asyncio.gather(*[analyze_package(package, semaphore) for package in packages])

def main():
    packages = get_packages()
    """
    for package in packages:
        if analyze_package(package):
            print("Setuptools not detected")
        else:
            print("Setuptools detected")
        exit()
    """
    print(list(packages)[:15])
    results = asyncio.run(report(list(packages)[:15]))
    # print(list(packages))
    # results = asyncio.run(report(list(packages)))
    print(results)
if __name__ == "__main__":
    main()
