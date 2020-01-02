class __UnresolvedPlaceholder(object):
  pass
UnresolvedPlaceholder = __UnresolvedPlaceholder()

class PlaceholderError(KeyError):
  pass

class UDNResolveError(Exception):
  pass

# the idea is to have something that is always like None, but explodes when
# you try to use it as a string. this means that you can resolve placeholders
# and evaluate them in complex conditional expressions, allowing them to be
# hoisted, and still protect conditional access to the values
# it could also be that you might try to call the result - in that case, blow
# and exception as well.
class UndefinedPlaceholder(object):
  def __init__(self, name, available_placeholders):
    self.name = name
    self.available_placeholders = available_placeholders

  def __nonzero__(self):
    return False

  def __str__(self):
    raise PlaceholderError(self.name, self.available_placeholders)

  def __call__(self, *pargs, **kargs):
    raise PlaceholderError(self.name, self.available_placeholders)

class UndefinedAttribute(UndefinedPlaceholder):
  pass

def import_module_symbol(name):
  name_parts = name.split('.')
  module_name = '.'.join(name_parts[:-1])
  symbol_name = name_parts[-1]
  module = __import__(module_name, globals(), locals(), [symbol_name])
  try:
    symbol = getattr(module, symbol_name)
  except AttributeError, e:
    raise ImportError("can't import %s" % name)
  return symbol


# map template function names to python function names
# inject them into a module so they run as globals
def register_functions(module, template_function_map):
  for t_name, f_name in template_function_map.iteritems():
    f_func = import_module_symbol(f_name)
    setattr(module, t_name, f_func)
    
# decorate a function object so the value will be retrieved once and then
# cached in the template forever.
def cache_forever(function):
  function.cache_forever = True
  return function

# decorate a function object so its result is not cached in module globals
def never_cache(function):
	function.never_cache = True
	return function
