<center><img src="https://raw.githubusercontent.com/colav/colav.github.io/master/img/Logo.png"/></center>

# Kahi_plugins
Mono Repo for Kahi Plugins 

# Table of Contents
* [Plugin explanation](#explanation)
* [Anatomy of a plugin package](#anatomy)
* [Creating a plugin release](#release)
* [Final remarks](#remarks)

## Plugin explanation <a name="explanation"></a>
This repository allows to host all plugins for Kahi.
The directory `kahi_template` is a template project to with a basic example, 
every project works as a python package and the kahi plugin system works by name convention see ([python plugin docs](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-naming-convention))
in our case the name prefix is `Kahi_`

Instead copying the folder kahi_template, you can run the next command to create you new plugin directory.
```sh
kahi_run --generate_plugin myplugin
```
this is going to create a directory called  **Kahi_myplugin*

## Anatomy of a plugin package <a name="anatomy"></a>
The packages have to have the next structure
```
Kahi_myplugin
kahi_myplugin/README.md
Kahi_myplugin/kahi_myplugin
Kahi_myplugin/kahi_myplugin/__init__.py
Kahi_myplugin/kahi_myplugin/kahi_myplugin.py
Kahi_myplugin/kahi_myplugin/_version.py
Kahi_myplugin/MANIFEST.in
Kahi_myplugin/setup.py
```


The plugin have to be child class of **KahiBase**,
in the template you will find a file kahi_myplugin.py with a class Kahi_myplugin, 
as example.

The parameters for configuration have to be defined right before the class as class variable or class attribute  see ([python doc](https://docs.python.org/3/tutorial/classes.html#class-and-instance-variables))
```py
from kahi.KahiBase import KahiBase

class Kahi_myplugin(KahiBase):
    # class implementation
```


# Creating a plugin release <a name="release"></a>
We have a github action that allow to create a release for any plugin in the mono repo.
* The first thing is to update the version of your plugin on 
`Kahi_myplugin/kahi_myplugin/_version.py`
* Lets go to [https://github.com/colav/Kahi_plugins/releases](https://github.com/colav/Kahi_plugins/releases) and click in **draf a new release**
* Click in choose new tag and write `Kahi_mypluigin/v0.0.x` name of your plugin slash the version of your plugin
* Write the release notes
* click on publish relase

Now the github action will be activate and you can check the status of you package here[https://github.com/colav/Kahi_plugins/actions/workflows/kahi-plugin-publish.yml](https://github.com/colav/Kahi_plugins/actions/workflows/kahi-plugin-publish.yml)

# Final remarks <a name="remarks"></a>
* You can take a look in the already developed plugins to have examples or get inspiration for your plugins.
* Remember write elegant documentation for your plugins.
* if you need help please open an issue.

Made with love ❤️ by Colav Team! 😃.
