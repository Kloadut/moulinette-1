# -*- coding: utf-8 -*-

import os
import ldap
import ldap.modlist as modlist
import json
import re
import getpass
import random
import string
import gettext
import getpass

win = []

def random_password(length=8):
    char_set = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.sample(char_set,length))

def colorize(astr, color):
    """
    Print with style ;)

    Keyword arguments:
        astr    -- String to colorize
        color   -- Name of the color

    """
    color_dict = {
        'red'   : '31',
        'green' : '32',
        'yellow': '33',
        'cyan'  : '34',
        'purple': '35'
    }
    return "\033["+ color_dict[color] +"m\033[1m" + astr + "\033[m"

def pretty_print_dict(d, depth=0):
    for k,v in sorted(d.items(), key=lambda x: x[0]):
        k = colorize(str(k), 'purple')
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print(("  ") * depth + ("%s: " % str(k)))
            pretty_print_dict(v, depth+1)
        elif isinstance(v, list):
            print(("  ") * depth + ("%s: " % str(k)))
            for key, value in enumerate(v):
                if isinstance(value, tuple):
                    pretty_print_dict({value[0]: value[1]}, depth+1)
                elif isinstance(value, dict):
                    pretty_print_dict({key: value}, depth+1)
                else:
                    print(("  ") * (depth+1) + "- " +str(value))
        else:
            if not isinstance(v, basestring):
                v = str(v)
            print(("  ") * depth + "%s: %s" % (str(k), v))

def is_true(arg):
    true_list = ['yes', 'Yes', 'true', 'True' ]
    for string in true_list:
        if arg == string:
            return True

    return False

def win_msg(astr):
    """
    Display a success message if isatty

    Keyword arguments:
        astr -- Win message to display

    """
    global win
    if os.isatty(1):
        print('\n' + colorize(_("Success: "), 'green') + astr + '\n')

    win.append(astr)


def validate(pattern, array):
    """
    Validate attributes with a pattern

    Keyword arguments:
        pattern -- Regex to match with the strings
        array -- List of strings to check

    Returns:
        Boolean | YunoHostError

    """
    if array is None:
        return True
    if isinstance(array, str):
        array = [array]
    for string in array:
        if re.match(pattern, string):
            pass
        else:
            raise YunoHostError(22, _('Invalid attribute') + ' ' + string)
        return True

def get_required_args(args, required_args, password=False):
    """
    Input missing values or raise Exception

    Keyword arguments:
       args -- Available arguments
       required_args -- Dictionary of required arguments and input phrase
       password -- True|False Hidden password double-input needed

    Returns:
        args

    """
    try:
        for arg, phrase in required_args.items():
            if not args[arg] and arg != 'password':
                if os.isatty(1):
                    args[arg] = raw_input(colorize(phrase + ': ', 'cyan'))
                else:
                    raise Exception #TODO: fix
        # Password
        if 'password' in required_args and password:
            if not args['password']:
                if os.isatty(1):
                    args['password'] = getpass.getpass(colorize(required_args['password'] + ': ', 'cyan'))
                    pwd2 = getpass.getpass(colorize('Retype ' + required_args['password'][0].lower() + required_args['password'][1:] + ': ', 'cyan'))
                    if args['password'] != pwd2:
                        raise YunoHostError(22, _("Passwords doesn't match"))
                else:
                    raise YunoHostError(22, _("Missing arguments"))
    except KeyboardInterrupt, EOFError:
        raise YunoHostError(125, _("Interrupted"))

    return args


def display_error(error, json_print=False):
    """
    Nice error displaying

    """
    if not __debug__ :
        traceback.print_exc()
    if os.isatty(1) and not json_print:
        print('\n' + colorize(_("Error: "), 'red') + error.message)
    else:
        print(json.dumps({ error.code : error.message }))


class YunoHostError(Exception):
    """
    Custom exception

    Keyword arguments:
        code    -- Integer error code
        message -- Error message to display

    """
    def __init__(self, code, message):
        code_dict = {
            1   : _('Fail'),
            13  : _('Permission denied'),
            17  : _('Already exists'),
            22  : _('Invalid arguments'),
            87  : _('Too many users'),
            111 : _('Connection refused'),
            122 : _('Quota exceeded'),
            125 : _('Operation canceled'),
            167 : _('Not found'),
            168 : _('Undefined'),
            169 : _('LDAP operation error')
        }
        self.code = code
        self.message = message
        if code_dict[code]:
            self.desc = code_dict[code]
        else:
            self.desc = code


class Singleton(object):
    instances = {}
    def __new__(cls, *args, **kwargs):
        if cls not in cls.instances:
            cls.instances[cls] = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls.instances[cls]


class YunoHostLDAP(Singleton):
    """ Specific LDAP functions for YunoHost """
    pwd = False
    connected = False
    conn = ldap.initialize('ldap://localhost:389')
    base = 'dc=yunohost,dc=org'
    level = 0

    def __enter__(self):
        return self

    def __init__(self, password=False, anonymous=False):
        """
        Connect to LDAP base

        Initialize to localhost, base yunohost.org, prompt for password

        """
        if anonymous:
           self.conn.simple_bind_s()
           self.connected = True
        elif self.connected and not password:
           pass
        else:
            if password:
                self.pwd = password
            elif self.pwd:
                pass
            else:
                try:
                    with open('/etc/yunohost/passwd') as f:
                        self.pwd = f.read()
                except IOError:
                    need_password = True
                    while need_password:
                        try:
                            self.pwd = getpass.getpass(colorize(_('Admin Password: '), 'yellow'))
                            self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
                        except KeyboardInterrupt, EOFError:
                            raise YunoHostError(125, _("Interrupted"))
                        except ldap.INVALID_CREDENTIALS:
                            print(_('Invalid password... Try again'))
                        else:
                            need_password = False

            try:
                self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
                self.connected = True
            except ldap.INVALID_CREDENTIALS:
                raise YunoHostError(13, _('Invalid credentials'))

        self.level = self.level+1

    def __exit__(self, type, value, traceback):
        self.level = self.level-1
        if self.level == 0:
            try: self.disconnect()
            except: pass

    def disconnect(self):
        """
        Unbind from LDAP

        Returns
            Boolean | YunoHostError

        """
        try:
            self.connected = False
            self.pwd = False
            self.conn.unbind_s()
        except:
            raise YunoHostError(169, _('An error occured during disconnection'))
        else:
            return True


    def search(self, base=None, filter='(objectClass=*)', attrs=['dn']):
        """
        Search in LDAP base

        Keyword arguments:
            base    -- Base to search into
            filter  -- LDAP filter
            attrs   -- Array of attributes to fetch

        Returns:
            Boolean | Dict

        """
        if not base:
            base = self.base

        try:
            result = self.conn.search_s(base, ldap.SCOPE_SUBTREE, filter, attrs)
        except:
            raise YunoHostError(169, _('An error occured during LDAP search'))

        if result:
            result_list = []
            for dn, entry in result:
                if attrs != None:
                    if 'dn' in attrs:
                        entry['dn'] = [dn]
                result_list.append(entry)
            return result_list
        else:
            return False


    def add(self, rdn, attr_dict):
        """
        Add LDAP entry

        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        ldif = modlist.addModlist(attr_dict)

        try:
            self.conn.add_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry creation'))
        else:
            return True

    def remove(self, rdn):
        """
        Remove LDAP entry

        Keyword arguments:
            rdn         -- DN without domain

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        try:
            self.conn.delete_s(dn)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry deletion'))
        else:
            return True


    def update(self, rdn, attr_dict, new_rdn=False):
        """
        Modify LDAP entry

        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add
            new_rdn     -- New RDN for modification

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        actual_entry = self.search(base=dn, attrs=None)
        ldif = modlist.modifyModlist(actual_entry[0], attr_dict, ignore_oldexistent=1)

        try:
            if new_rdn:
                self.conn.rename_s(dn, new_rdn)
                dn = new_rdn + ',' + self.base

            self.conn.modify_ext_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry update'))
        else:
            return True


    def validate_uniqueness(self, value_dict):
        """
        Check uniqueness of values

        Keyword arguments:
            value_dict -- Dictionnary of attributes/values to check

        Returns:
            Boolean | YunoHostError

        """
        for attr, value in value_dict.items():
            if not self.search(filter=attr + '=' + value):
                continue
            else:
                raise YunoHostError(17, _('Attribute already exists') + ' "' + attr + '=' + value + '"')
        return True
