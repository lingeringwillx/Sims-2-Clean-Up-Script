import datetime
import dbpf
import os
import sys

def log(text):
    print(text)
    with open('cleanup_log.txt', 'a') as log_file:
        log_file.write(text + '\n')
        
def get_total_size():
    total = 0
    for pack in packs:
        for root, dirs, files in os.walk(os.path.join(base_dir, pack.path)):
            for file in files:
                total += os.path.getsize(os.path.join(root, file))
                
    return total / 1024 ** 3 #GB
    
#relative path to file excluding pack folder
def get_key(file_path, pack):
    key = os.path.relpath(file_path, os.path.join(base_dir, pack.path))
    #base game has a different folder name for the game assets
    if key.startswith('TSData\\Res\\Sims3D'):
        key = key.replace('Sims3D', '3D')
        
    return key
    
#for expansion and stuff pack information
class Pack:
    def __init__(self, name, code, date, path):
        self.name = name
        self.code = code
        self.date = date
        self.path = path
        self.entries_set = {}
        
    def __repr__(self):
        return '{}, {}'.format(self.name, self.date)
        
packs = []

#expansion packs
packs.append(Pack('Base', 'Base', datetime.date(2004, 9, 14), 'Double Deluxe\\Base'))
packs.append(Pack('University', 'EP1', datetime.date(2005, 3, 1), 'University Life\\EP1'))
packs.append(Pack('Nightlife', 'EP2', datetime.date(2005, 9, 13), 'Double Deluxe\\EP2'))
packs.append(Pack('Open for Business', 'EP3', datetime.date(2006, 3, 2), 'Best of Business\\EP3'))
packs.append(Pack('Pets', 'EP4', datetime.date(2006, 10, 18), 'Fun with Pets\\EP4'))
packs.append(Pack('Seasons', 'EP5', datetime.date(2007, 3, 1), 'Seasons'))
packs.append(Pack('Bon Voyage', 'EP6', datetime.date(2007, 9, 4), 'Bon Voyage'))
packs.append(Pack('FreeTime', 'EP7', datetime.date(2008, 2, 26), 'Free Time'))
packs.append(Pack('Apartment Life', 'EP8', datetime.date(2008, 8, 26), 'Apartment Life'))

#stuff packs
packs.append(Pack('Family Fun Stuff', 'SP1', datetime.date(2006, 4, 13), 'Fun with Pets\\SP1'))
packs.append(Pack('Glamour Life Stuff', 'SP3', datetime.date(2006, 8, 31), 'Glamour Life Stuff'))
packs.append(Pack('Celebration! Stuff', 'SP4', datetime.date(2007, 4, 3), 'Double Deluxe\\SP4'))
packs.append(Pack('H&M Fashion Stuff', 'SP5', datetime.date(2007, 6, 5), 'Best of Business\\SP5'))
packs.append(Pack('Teen Style Stuff', 'SP6', datetime.date(2007, 9, 5), 'University Life\\SP6'))
packs.append(Pack('Kitchen & Bath Interior Design Stuff', 'SP7', datetime.date(2008, 4, 15), 'Best of Business\\SP7'))
packs.append(Pack('IKEA Home Stuff', 'SP8', datetime.date(2008, 6, 24), 'University Life\\SP8'))
packs.append(Pack('Mansions & Garden Stuff', 'SP9', datetime.date(2008, 9, 17), 'Fun with Pets\\SP9'))

packs.sort(key=lambda pack: pack.date) #sort by date

#game directory:
base_dir = sys.argv[1]

if not os.path.isdir(base_dir):
    raise FileNotFoundError('Directory {} not found'.format(base_dir))
    
#remove pack from list if not found in directory
for pack in packs:
    if not os.path.isdir(os.path.join(base_dir, pack.path)):
        packs.remove(pack)
        
if len(packs) == 0:
    raise FileNotFoundError('No expansion packs or stuff packs found in {}'.format(base_dir))
    
#delete log from last run
if os.path.isfile('cleanup_log.txt'):
    os.remove('cleanup_log.txt')
    
total_old = get_total_size()

#collect infromation on the types, groups, instances, and resources (TGIRs) of entries found in package files
#later, we will be checking newer EPs and SPs for matching TGIRs and if a match is found, then we will delete the entry from the older package files
#starting from the last pack
for i in reversed(range(len(packs))):
    pack = packs[i]
    last_pack = i == len(packs) - 1
    
    if not last_pack:
        log(pack.name)
        
    for root, dirs, files in os.walk(os.path.join(base_dir, pack.path)):
        for file in files:
            if file.endswith('.package'):
                file_path = os.path.join(root, file)
                package = dbpf.Package.unpack(file_path)
                
                #the entries set is a dictionary with the keys being the names of the package files found in each SP/EP, each value is a set of tuples containing the TGIRs of each entry in the package
                #we can exploit fast dictionary and set lookups to find out if a certain TGIR exists in a certain package file
                key = get_key(file_path, pack)
                pack.entries_set[key] = set()
                
                #looping from the end of the package to avoid the problems that occur to the list when popping elements while looping
                changed = False
                for j in reversed(range(len(package.entries))):
                    entry = package.entries[j]
                    
                    #don't add the directory of compressed files
                    if entry.type != 0xE86B1EEF:
                        #add entry info to entries_set
                        if 'resource' in entry:
                            tgir = (entry.type, entry.group, entry.instance, entry.resource)
                        else:
                            tgir = (entry.type, entry.group, entry.instance)
                            
                        pack.entries_set[key].add(tgir)
                        
                        #we check against newer expansions, and if the same entry exists in a later expansion, then we can delete it from the older expansion
                        #remember, the packs list has been sorted by date from the oldest date to the newest date
                        for pack2 in packs[(i + 1):]:
                            if key in pack2.entries_set and tgir in pack2.entries_set[key]:
                                package.entries.pop(j)
                                changed = True
                                break
                                
                if changed:
                    n_entries = len(package.entries)
                    
                    #if the package has no entries remaining, or only the directory of compressed files remains then delete the file
                    if n_entries == 0 or (n_entries == 1 and package.entries[0].type == 0xE86B1EEF):
                        size = os.path.getsize(file_path) / (1024 ** 2)
                        os.remove(file_path)
                        log('{}, {:0.2f} MB -> 0.00 MB'.format(os.path.relpath(file_path, base_dir), size))
                        
                    #otherwise write the new package with removed redundant entries into a temporary file, then overwrite the original file (safer file writing procedure)
                    else:
                        old_size = os.path.getsize(file_path) / (1024 ** 2)
                        
                        temp_path = file_path.rsplit('.', 1)[0] + '.tmp'
                        package.pack_into(temp_path)
                        os.replace(temp_path, file_path)
                        
                        new_size = os.path.getsize(file_path) / (1024 ** 2)
                        log('{}, {:0.2f} MB -> {:0.2f} MB'.format(os.path.relpath(file_path, base_dir), old_size, new_size))
                        
    if not last_pack:
        log('')
            
#delete empty directories
for root, dirs, files in os.walk(base_dir, topdown=False):
    if len(dirs) + len(files) == 0:
        os.rmdir(root)
        
#get new game size
total_new = get_total_size()
log('Total: {:0.2f} GB -> {:0.2f} GB, {:0.2f} GB, {:0.2f}%\n'.format(total_old, total_new, total_old - total_new, total_new / total_old * 100))