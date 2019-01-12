from distutils.core import setup
with open('README.md') as infile:
    long_description = infile.read()

setup(
    name='blllib',
    packages=['blllib'],
    version='1.0.1',
    license='MIT',
    description='Batched concurrent pipeline',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Kaiwen Wu',
    author_email='kps6326@hotmail.com',
    url='https://github.com/kkew3/blllib',
    keywords=['pipeline', 'parallel'],
    classifiers=[
        'Topic :: Software Development',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
