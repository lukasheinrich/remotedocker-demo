from setuptools import setup, find_packages

setup(
    name = 'remotedocker-demo',
    version = '0.0.1',
    author = 'Lukas Heinrich',
    packages = find_packages(),
    install_requires = [
        'zmq',
        'requests',
        'click',
    ],
    entry_points = {
      'console_scripts': ['remotedocker=remotedocker.client:client'],
    },
    extras_require = {
        'ssh':  ["pexpect"],
	'server': ['flask']
    }
)