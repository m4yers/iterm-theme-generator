"""Setup for iterm theme generator."""

import io
import setuptools

def requirements():
  with io.open('./requirements.txt') as out:
    return out.read()


def version():
  with io.open('./VERSION') as out:
    return out.read()


def readme():
  with io.open('./README.rst') as out:
    return out.read()


setuptools.setup(
    name='iterm-theme-generator',
    version=version(),
    description='Generate iTerm2 colors from an image',
    long_description=readme(),
    license='MIT',
    author='Artyom Goncharov',
    author_email='m4yers@gmail.com',
    url='https://github.com/m4yers/iterm-theme-generator',
    keywords='iterm, iterm2, colors, theme, image, wallpaper',
    install_requires=requirements(),
    python_requires='>=2.7, <3',
    packages=setuptools.find_packages(),
    data_files=[('.',['README.rst', 'requirements.txt', 'LICENSE', 'VERSION'])],
    entry_points={'console_scripts': ['iterm_theme_generator=iterm_theme_generator.__main__:main']},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
    ])
