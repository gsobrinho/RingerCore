__all__ = [ 'argparse','ArgumentParser']

from RingerCore.util import get_attributes
import re

try:
  import argparse
except ImportError:
  from RingerCore.parsers import __py_argparse as argparse

from RingerCore.Configure import BooleanStr, EnumStringification

class _EraseGroup( Exception ):
  """
  Indicate that a group should be erased.
  """
  pass

class _ActionsContainer( object ):

  def add_argument(self, *args, **kwargs):
    if 'type' in kwargs:
      lType = kwargs['type']
      if issubclass(lType, EnumStringification):
        # Make sure that there will be registered the type and the action that
        # will be used for it:
        if not lType in self._registries['type']:
          self.register('type', lType, lType.retrieve)
        # Deal with the help option:
        help_str = kwargs.pop('help','').rstrip(' ')
        if not '.' in help_str[-1:]: help_str += '. '
        if help_str[-1:] != ' ': help_str += ' '
        help_str += "Possible options are: "
        from operator import itemgetter
        val = sorted(get_attributes( kwargs['type'], getProtected = False), key=itemgetter(1))
        help_str += str([v[0] for v in val])
        help_str += ', or respectively equivalent to the integers: '
        help_str += str([v[1] for v in val])
        kwargs['help'] = help_str
        # Deal with BooleanStr special case:
        if issubclass(lType, BooleanStr):
          if kwargs.pop('nargs','?') != '?':
            raise ValueError('Cannot specify nargs different from \'?\' when using boolean argument')
          kwargs['nargs'] = '?'
          kwargs['const'] = BooleanStr.retrieve( kwargs.pop('const','True') )
    argparse._ActionsContainer.add_argument(self, *args, **kwargs)

  def add_argument_group(self, *args, **kwargs):
    group = _ArgumentGroup(self, *args, **kwargs)
    self._action_groups.append(group)
    return group

  def add_mutually_exclusive_group(self, **kwargs):
    group = _MutuallyExclusiveGroup(self, **kwargs)
    self._mutually_exclusive_groups.append(group)
    return group

  def delete_arguments(self, *vars_, **kw):
    "Remove all specified arguments from the parser"
    # Remove arguments from the groups:
    popIdxs = []
    _visited_groups = kw.pop('_visited_groups',[])
    for idx, group in enumerate(self._action_groups):
      try:
        if group in _visited_groups:
          raise _EraseGroup()
        _visited_groups.append( group )
        group.delete_arguments( *vars_, _visited_groups = _visited_groups )
      except _EraseGroup:
        popIdxs.append(idx)
    for idx in reversed(popIdxs):
      #print 'deleting group:', self._action_groups[idx].title 
      self._action_groups.pop( idx )
    popIdxs = []
    # Repeat procedure for the mutually exclusive groups:
    _visited_mutually_exclusive_groups = kw.pop('_visited_mutually_exclusive_groups',[])
    for idx, group in enumerate(self._mutually_exclusive_groups):
      try:
        if group in _visited_mutually_exclusive_groups:
          raise _EraseGroup()
        _visited_mutually_exclusive_groups.append(group)
        group.delete_arguments( *vars_, _visited_mutually_exclusive_groups = _visited_mutually_exclusive_groups )
      except _EraseGroup:
        popIdxs.append(idx)
    for idx in reversed(popIdxs):
      #print 'deleting mutually exclusive group:', self._mutually_exclusive_groups[idx].title 
      self._mutually_exclusive_groups.pop( idx )
    # Treat our own actions:
    popIdxs = []
    for var in vars_:
      for idx, action in enumerate(self._actions):
        if action.dest == var:
          popIdxs.append( idx )
          popOptKeys = []
          for optKey, optAction in self._option_string_actions.iteritems():
            if optAction.dest == var:
              popOptKeys.append(optKey)
          for popOpt in reversed(popOptKeys):
            #print "(delete) poping key:", popOpt
            self._option_string_actions.pop(popOpt)
          break
    popIdxs = sorted(popIdxs)
    for idx in reversed(popIdxs):
      #print "(delete) popping action,", idx, self._actions[idx].dest
      self._actions.pop(idx)
    # Raise if we shouldn't exist anymore:
    if isinstance(self, (_MutuallyExclusiveGroup, _ArgumentGroup)) and \
       not self._group_actions and \
       not self._defaults:
       raise _EraseGroup()

  def suppress_arguments(self, **vars_):
    """
    Suppress all specified arguments from the parser by assigning a default
    value to them. It must be specified through a key, value pair, the key
    being the variable destination, and the value the value it should always
    take.
    """
    _visited_groups = vars_.pop('_visited_groups',[])
    for idx, group in enumerate(self._action_groups):
      if group in _visited_groups:
        #print 'already visited group:', group.title, "|(", idx, "/", len(self._action_groups), ")"
        continue
      _visited_groups.append(group)
      #print "supressing:", group.title, "|(", idx, "/", len(self._action_groups), ")"
      group.suppress_arguments( _visited_groups = _visited_groups, **vars_)
    _visited_mutually_exclusive_groups = vars_.pop('_visited_mutually_exclusive_groups',[])
    for idx, group in enumerate(self._mutually_exclusive_groups):
      if group in _visited_mutually_exclusive_groups:
        #print '(mutually) already visited group:', group.title, "|(", idx, "/", len(self._mutually_exclusive_groups), ")"
        continue
      _visited_mutually_exclusive_groups.append(group)
      #print "(mutually) supressing:", group.title, "|(", idx, "/", len(self._mutually_exclusive_groups), ")"
      group.suppress_arguments( _visited_mutually_exclusive_groups = _visited_mutually_exclusive_groups, **vars_)
    popIdxs = []
    for var, default in vars_.iteritems():
      for idx, action in enumerate(self._actions):
        if action.dest == var:
          popIdxs.append( idx )
          popOptKeys = []
          for optKey, optAction in self._option_string_actions.iteritems():
            if optAction.dest == var:
              popOptKeys.append(optKey)
          for popOpt in reversed(popOptKeys):
            #print "poping key:", popOpt
            self._option_string_actions.pop(popOpt)
          break
    popIdxs = sorted(popIdxs)
    for idx in reversed(popIdxs):
      #print "popping action,", idx, self._actions[idx].dest
      self._actions.pop(idx)
    # Set defaults:
    self.set_defaults(**vars_)

  def get_groups(self, **kw):
    """
    Returns a list containing all groups within this object
    """
    groups = self._action_groups
    groups.extend( self._mutually_exclusive_groups )
    return groups

  def make_adjustments(self):
    """
    Remove empty groups
    """
    groups = self.get_groups()
    toEliminate = set()
    for idx, group in enumerate(groups):
      if idx in toEliminate:
        continue
      if not group._group_actions:
        #for key in group._defaults.keys():
        #  if key in self._defaults:
        #    group._defaults.pop(key)
        #self.set_defaults(**group._defaults)
        toEliminate |= {idx,}
        continue
      # This seems not to be needed as the argparse deals with it:
      ##Make sure that we have all grouped arguments with common titles
      ##merged in only one group. This avoids having several properties 
      #sameTitleIdxs = [idx + qidx for qidx, qgroup in enumerate(groups[idx:]) if group.title == qgroup.title and qgroup is not group]
      #for sameTitleIdx in sameTitleIdxs:
      #  # Add actions:
      #  group._actions.extend([action for action in groups[sameTitleIdxs]._actions if action not in group._actions])
      #  # And optinal strings
      #  group._option_string_actions.update({item for item in groups[sameTitleIdxs]._option_string_actions if not item[0] in group._option_string_actions})
      #  # Sign it to be eliminated
      #  toEliminate |= {sameTitleIdx,}
    # Now eliminate the groups
    lActions = len(self._action_groups)
    for idx in reversed(list(toEliminate)):
      if idx < lActions:
        #print "(adjustments) eliminating:", self._action_groups[idx].title
        self._action_groups.pop(idx)
      else:
        #print "(adjustments) eliminating mutually exclusive:", self._mutually_exclusive_groups[idx].title
        self._mutually_exclusive_groups.pop(idx-lActions)

class ArgumentParser( _ActionsContainer, argparse.ArgumentParser ):
  """
  This class has the following extra features over the original ArgumentParser:

  -> add_boolean_argument: This option can be used to declare an argument which
  may be declared as a radio button, that is, simply:
     --option
  where it will be set to True, or also specifying its current status through the
  following possible ways:
     --option True
     --option true
     --option 1
     --option 0
     --option False
     --option false

  -> When type is a EnumStringification, it will automatically transform the input
  value using retrieve;
  """

  def __init__(self,*l,**kw):
    _ActionsContainer.__init__(self)
    argparse.ArgumentParser.__init__(self,*l,**kw)
    self.register('type', BooleanStr, BooleanStr.retrieve)
    if 'parents' in kw:
      parents = kw['parents']
      for parent in parents:
        for key, reg in parent._registries.iteritems():
          if not key in self._registries:
            self._registries[key] = reg
          else:
            for key_act, act in reg.iteritems():
              if not key_act in self._registries[key]:
                self.register(key, key_act, act)


class _ArgumentGroup( _ActionsContainer, argparse._ArgumentGroup ):
  def __init__(self, *args, **kw):
    _ActionsContainer.__init__(self)
    argparse._ArgumentGroup.__init__(self,*args,**kw)
    self.register('type', BooleanStr, BooleanStr.retrieve)

class _MutuallyExclusiveGroup( _ActionsContainer, argparse._MutuallyExclusiveGroup ):
  def __init__(self, *args, **kw):
    _ActionsContainer.__init__(self)
    argparse._MutuallyExclusiveGroup.__init__(self,*args,**kw)
    self.register('type', BooleanStr, BooleanStr.retrieve)
