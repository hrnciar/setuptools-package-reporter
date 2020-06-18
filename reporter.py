#!/bin/python3

from subprocess import PIPE, run
from glob import glob
import asyncio
import os
import logging
import shutil

def get_packages():
    """
    Return list of packages that requires python3-devel
    and at the same time does not requires python3-setuptools
    """
    command = ['repoquery', '-q', '--repo=rawhide rawhide-source', '--whatrequires=python3-devel', '--archlist=src']
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    packages_with_devel = set(result.stdout.split(sep='\n'))
    command = ['repoquery', '-q','--repo=rawhide rawhide-source', '--whatrequires=python3-setuptools', '--archlist=src']
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    packages_with_setuptools = set(result.stdout.split(sep='\n'))

    packages = packages_with_devel - packages_with_setuptools
    package_names = set()
    for package in packages:
        package_names.add(package.rsplit("-", 2)[0])

    return package_names



async def report(packages):
    semaphore = asyncio.Semaphore(10)
    async def analyze_package(package, semaphore):
        async with semaphore:
            try:
                cmd = f"cd /tmp && fedpkg clone {package} && cd {package} && fedpkg prep"
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)

                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    logging.error("fedpkg clone or prep failed.")
                    logging.error(f'[stderr]\n{stderr.decode()}')
                    return None

                rules = [f"grep -r -i --include='*.py' 'from setuptools import' /tmp/{package}",
                        f"grep -r -i --include='*.py' 'import setuptools' /tmp/{package}",
                        f"grep -r -i --include='*.py' 'setuptools' /tmp/{package}"]
                for cmd in rules:
                    proc = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE)

                    stdout, stderr = await proc.communicate()

                    logging.info(f'{package} exited with {proc.returncode}')
                    if stdout:
                        logging.info(f'[stdout]\n{stdout.decode()}')
                    if stderr:
                        (f'[stderr]\n{stderr.decode()}')
                    if proc.returncode == 0:
                        if cmd == f"grep -r -i --include='*.py' 'setuptools' /tmp/{package}":
                            return 2
                        else:
                            return 1
                return 0
            finally:
                try:
                    shutil.rmtree(f'/tmp/{package}')
                except:
                    pass

        # 0 - package does not use setuptools
        # 1 - package use setuptools
        # 2 - there is 'setuptools' in sourcecode but it doesn't have to be relevant
        # None - package failed to be analyzed

    return await asyncio.gather(*[analyze_package(package, semaphore) for package in packages])

def main():
    logging.basicConfig(filename='report.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    packages = get_packages()
    logging.info("Number of packages to be processed: %s", str(len(packages)))
    print(list(packages))
    return_codes = asyncio.run(report(list(packages)))
    results = dict(zip(packages, return_codes))
    print(results)
    packages_with_setuptools = []
    packages_without_setuptools = []
    packages_with_not_relevant_setuptools = []
    failed_packages = []
    for package, return_code in results.items():
        if return_code == 0:
            packages_without_setuptools.append(package)
        elif return_code == 1:
            packages_with_setuptools.append(package)
        elif return_code == 2:
            packages_with_not_relevant_setuptools.append(package)
        else:
            failed_packages.append(package)
    print("There is " + str(len(packages_without_setuptools)) + " packages without any mention of 'setuptools'.")
    print(packages_without_setuptools)
    print("There is " + str(len(packages_with_setuptools)) + " packages with relevant mention of 'setuptools'.")
    print(packages_with_setuptools)
    print("There is " + str(len(packages_with_not_relevant_setuptools)) + " packages with not relevant mention of 'setuptools'.")
    print(packages_with_not_relevant_setuptools)
    print("There is " + str(len(failed_packages)) + " packages which failed to be tested (eg. fedpkg clone/prep failure).")
    print(failed_packages)
if __name__ == "__main__":
    main()
