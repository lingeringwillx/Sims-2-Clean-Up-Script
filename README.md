# Sims 2 Clean Up Script

This is an experimental script that reduces the size of the game by removing redundant/unused entries from the files of the Sims 2 Ultimate Collection.

It eliminates approximately 2.44 GB worth of data from the game, which is about 20% of the game's size.

It uses my [sims2py](https://github.com/lingeringwillx/sims2py) and [structio](https://github.com/lingeringwillx/StructIO) libraries.

### Assumptions

The game checks the files for each stuff pack and expansion pack in release order, and when it finds two entries in different package files with a matching type, group, instance, and resource ids it overrides the entry from the older pack with the entry from the newer pack, which means that the older entry is not needed any more and can be deleted without causing any problems (unless the player wants to run an older expansion).

### Usage

Run the script with the first argument being the game's directory.

`python cleanup.py game_directory`

If your game directory is in `C:\\Program Files` then you might need to copy the files to another locaton first.

### Known Issues

There are some known difficulties with using SimPE for mesh extraction on the cleaned files. Also, you will not be able to access older versions of behavior files as those have been deleted. Hence, for CC makers and modders, it's better to use the full game.
