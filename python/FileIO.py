__all__ = ['save', 'load', 'expandFolders', 'mkdir_p',
           'getExtension', 'checkExtension', 'changeExtension',
           'ensureExtension', 'appendToFileName', 'findFile',
           'getMD5','checkFile', 'WriteMethod', 'cat_files_py',
           'getFiles']

import numpy as np
import cPickle
import gzip
import tarfile
import tempfile
import os
import sys
import shutil
import StringIO
from time import sleep, time

def save(o, filename, **kw):
  """
    Save an object to disk.
  """
  compress = kw.pop( 'compress', True )
  protocol = kw.pop( 'protocol', -1   )
  if not isinstance(filename, str):
    raise("Filename must be a string!")
  filename = os.path.abspath( os.path.expanduser( os.path.expandvars( path ) ) )
  dirplace = os.path.dirname(filename)
  if not os.path.isdir( dirplace ) and dirplace:
    mkdir_p( dirplace )
  if type(protocol) is str:
    if protocol == "savez_compressed":
      filename = ensureExtension(filename, 'npz')
      if type(o) is dict:
        np.savez_compressed(filename, **o)
      else:
        if not isinstance(o, (list,tuple) ):
          o = (o,)
        np.savez_compressed(filename, *o)
    elif protocol == "savez":
      filename = ensureExtension(filename, 'npz')
      if type(o) is dict:
        np.savez(filename, **o)
      else:
        if not isinstance(o, (list,tuple) ):
          o = (o,)
        np.savez(filename, *o)
    elif protocol == "save":
      filename = ensureExtension(filename, 'npy')
      np.save(filename, o)
    else:
      raise ValueError("Unknown protocol '%s'" % protocol)
  elif type(protocol) is int:
    filename = ensureExtension(filename, 'pic')
    if compress:
      filename = ensureExtension(filename, 'gz')
      f = gzip.GzipFile(filename, 'wb')
    else:
      f = open(filename, 'w')
    cPickle.dump(o, f, protocol)
    f.close()
  return filename

def load(filename, decompress = 'auto', allowTmpFile = True, useHighLevelObj = False,
         useGenerator = False, tarMember = None, ignore_zeros = True, 
         extractAll = False, eraseTmpTarMembers = True,
         returnFileName = False, returnFileMember = False,
         logger = None):
  """
    Loads an object from disk.

    -> decompress: what protocol should be used to decompress the file.
    -> allowTmpFile: if to allow temporary files to improve loading speed.
    -> useHighLevelObj: automatic convert rawDicts to their python
       representation (not currently supported for numpy files.
    -> useGenerator: This option changes the behavior when loading a tarball
       file with multiple members. Instead returning a collection with all
       contents within the file, it will return a generator allowing each file
       to be read individually, thus reducing the amount of memory used in the
       process.
    -> tarMember: the tarMember in the tarfile to read. When not specified: read
    all.
    -> ignore_zeros: whether to ignore zeroed regions when reading tarfiles or
    not. This property is important for reading only one file from merged files
    in a fast manner.
    -> extractAll: expand every tar file members at once
    -> eraseTmpTarMembers: whether to erase tar members after reading them
    -> returnFileName: whether to return file name
    -> returnFileMember: whether to return file member object at the tar file
  """
  filename = os.path.abspath( os.path.expanduser( os.path.expandvars( path ) ) )
  transformDataRawData = __TransformDataRawData( useHighLevelObj, returnFileName, returnFileMember )
  if not os.path.isfile( filename ):
    raise ValueError("Cannot reach file %s" % filename )
  if checkExtension( filename, 'npy|npz'):
    o = transformDataRawData( np.load(filename,mmap_mode='r'), filename, None )
    return [o] if useGenerator else o
  else:
    if decompress == 'auto':
      if checkExtension( filename, 'tar.gz|tgz' ):
        decompress = 'tgz'
      elif checkExtension( filename, 'gz|gzip' ): 
        decompress = 'gzip'
      elif checkExtension( filename, 'tar' ):
        decompress = 'tar'
      elif checkExtension( filename, '.pic' ):
        decompress = False
      else:
        raise RuntimeError("It is not possible to read format: '.%s'. Input file was: '%s'." % (
          getExtension(filename, None), 
          filename) )
    if decompress == 'gzip':
      f = gzip.GzipFile(filename, 'rb')
    elif decompress in ('tgz', 'tar'):
      args = (allowTmpFile, transformDataRawData, 
              tarMember, extractAll, eraseTmpTarMembers,
              ignore_zeros, logger,)
      if decompress == 'tar':
        o = __load_tar(filename, 'r:', *args)
      else:
        o = __load_tar(filename, 'r:gz', *args)
      if not useGenerator:
        #o = list(map(lambda x: x[0], o))
        o = list(o)
        if len(o) == 1: o = o[0]
      return o
    else:
      f = open(filename,'r')
    o = cPickle.load(f)
    f.close()
    o = transformDataRawData( o, filename, None )
    return [o] if useGenerator else o
  # end of (if filename)
# end of (load) 


def __load_tar(filename, mode, allowTmpFile, transformDataRawData, tarMember,
               extractAll, eraseTmpTarMembers, ignore_zeros, logger = None):
  """
  Internal method for reading tarfiles
  """
  #useSubprocess = False
  useSubprocess = True
  if tarMember is None:
    f = tarfile.open(filename, mode, ignore_zeros = ignore_zeros)
    if not extractAll:
      if logger:
        logger.info("Retrieving tar file members (%s)...", "full" if ignore_zeros else "fast")
      memberList = f.getmembers()
  elif type(tarMember) in (tarfile.TarInfo, str):
    useSubprocess = True
    memberList = [tarMember]
  else:
    raise TypeError("tarMember argument must be TarInfo or None.")
  for entry in memberList if not extractAll else [None]:
    if allowTmpFile:
      tmpFolderPath=tempfile.mkdtemp()
      if useSubprocess:
        from subprocess import Popen, PIPE, CalledProcessError
        from RingerCore import is_tool
        tar_cmd = 'gtar' if is_tool('gtar') else 'tar'
        # TODO This will crash if someday someone uses a member in file that is
        # not in root path at the tarfile.
        if extractAll:
          start = time()
          logger.info("Proceeding to untar all members.")
          process_args = (tar_cmd, '--verbose', '-xvzif', filename,)
          untar_ps = Popen(process_args, stdout = PIPE, bufsize = 1, 
                          cwd = tmpFolderPath)
          memberList = []
          with untar_ps.stdout:
            while True:
              outputLine = untar_ps.stdout.readline().strip('\n')
              if outputLine == '':
                if untar_ps.poll() is not None:
                  break
              else:
                memberList.append(outputLine)
                logger.debug(outputLine)
          return_code = untar_ps.wait()
          if return_code != 0:
            raise CalledProcessError(return_code, process_args)
          from re import compile
          rexp = compile('\s+')
          memberList = [(int(size), name) for _, _, size, _, _, name in map(lambda member: rexp.split(member), memberList)]
          end = time()
          logger.info("Untar file content took %.2fs", end - start )
        else:
          memberName = entry.name if type(entry) is tarfile.TarInfo else entry
          untar_ps = Popen((tar_cmd, '--verbose', '-xvzif', filename, memberName,
                           ), stdout = PIPE, bufsize = 1, cwd = tmpFolderPath)
          with untar_ps.stdout:
            from re import compile
            rexp = compile('\s+')
            for line in iter(untar_ps.stdout.readline, b''):
              line = line.strip('\n')
              _, _, size, _, _, name = rexp.split(line)
              memberList = [(int(size), name)]
              break
        for entry in memberList:
          memberSize, memberName = (entry.size, entry.name, ) if type(entry) is tarfile.TarInfo else entry
          oFile = os.path.join( tmpFolderPath, memberName )
          while not os.path.isfile( oFile ):
            sleep(0.001)
          while os.path.getsize( oFile ) != memberSize:
            sleep(0.001)
          if not extractAll:
            untar_ps.kill()
            untar_ps.wait()
          os.listdir( tmpFolderPath )
          with open( oFile ) as f_member:
            data = transformDataRawData( cPickle.load(f_member), oFile if extractAll else filename, memberName )
            yield data
        if extractAll:
          break
      #else:
      #  if extractAll:
      #    logger.info("Untaring all members to %s...", tmpFolderPath)
      #    f.extractall(path=tmpFolderPath, )
      #  else:
      #    f.extractall(path=tmpFolderPath, members=(entry,))
      #  for entry in memberList if extractAll else [entry]:
      #    memberName = entry.name if type(entry) is tarfile.TarInfo else entry
      #    oFile = os.path.join(tmpFolderPath, memberName)
      #    print oFile
      #    with open(oFile) as f_member:
      #      yield transformDataRawData( cPickle.load(f_member), oFile if extractAll else filename, entry )
      #  if extractAll:
      #    break
      if eraseTmpTarMembers:
        shutil.rmtree(tmpFolderPath)
    else:
      fileobj = f.extractfile(entry)
      if checkExtension( entry.name, 'gz|gzip' ):
        fio = StringIO.StringIO( fileobj.read() )
        fileobj = gzip.GzipFile( fileobj = fio )
      yield transformDataRawData( cPickle.load(fileobj), filename, memberName )
  if not useSubprocess:
    f.close()
# end of (load_tar)

class __TransformDataRawData( object ):
  """
  Transforms raw data if requested to use high level object
  """

  def __init__(self, useHighLevelObj, returnFileName, returnFileMember,):
    self.useHighLevelObj = useHighLevelObj
    self.returnFileName = returnFileName
    self.returnFileMember = returnFileMember

  def __call__(self, o, fname, tmember):
    """
    Run transformation
    """
    if self.useHighLevelObj:
      from RingerCore.RawDictStreamable import retrieveRawDict
      from numpy.lib.npyio import NpzFile
      if type(o) is NpzFile:
        o = dict(o)
      o = retrieveRawDict( o )
    from RingerCore.util import appendToOutput
    o = appendToOutput( o, self.returnFileName,   fname   )
    o = appendToOutput( o, self.returnFileMember, tmember )
    return o

def expandFolders( pathList, filters = None, logger = None, level = None):
  """
    Expand all folders to the contained files using the filters on pathList

    Input arguments:

    -> pathList: a list containing paths to files and folders;
    filters;
    -> filters: return a list for each filter with the files contained on the
    list matching the filter glob.
    -> logger: whether to print progress using logger;
    -> level: logging level to print messages with logger;
  """
  if not isinstance( pathList, (list,tuple,) ):
    pathList = [pathList]
  from glob import glob
  if filters is None:
    filters = ['*']
  if not( type( filters ) in (list,tuple,) ):
    filters = [ filters ]
  retList = [[] for idx in range(len(filters))]
  from RingerCore.util import progressbar
  for path in progressbar( pathList, len(pathList), 'Expanding folders: ', 60, 50,
                           True if logger is not None else False, logger = logger,
                           level = level):
    path = os.path.abspath( os.path.expanduser( os.path.expandvars( path ) ) )
    if not os.path.exists( path ):
      raise ValueError("Cannot reach path '%s'" % path )
    if os.path.isdir(path):
      for idx, filt in enumerate(filters):
        cList = [ f for f in glob( os.path.join(path,filt) ) ]
        if cList: 
          retList[idx].extend(cList)
      folders = [ os.path.join(path,f) for f in os.listdir( path ) if os.path.isdir( os.path.join(path,f) ) ]
      if folders:
        recList = expandFolders( folders, filters )
        if len(filters) is 1:
          recList = [recList]
        for idx, l in enumerate(recList):
          retList[idx].extend(l)
    else:
      for idx, filt in enumerate(filters):
        if path in glob( os.path.join( os.path.dirname( path ) , filt ) ):
          retList[idx].append( path )
  if len(filters) is 1:
    retList = retList[0]
  return retList
 
def getExtension( filename, nDots = None):
  """
    Get file extension.

    Inputs:
    -> filename;
    -> nDots: the maximum number of dots extesions should have.
  """
  filename = filename.split('.')
  lParts = len(filename)
  if nDots is None: nDots = (lParts - 1)
  nDots = - nDots
  if nDots <= -lParts: nDots = - (lParts - 1)
  if nDots > -1:
    return ''
  return '.'.join(filename[nDots:])

def checkExtension( filename, ext, ignoreNumbersAfterExtension = True):
  """
    Check if file matches extension(s) ext. If checking for multiple
    extensions, use | to separate the extensions.
  """
  return bool(__extRE(ext, ignoreNumbersAfterExtension).match( filename ))

def __extRE(ext, ignoreNumbersAfterExtension = True):
  """
  Returns a regular expression compiled object that will search for
  extension ext
  """
  import re
  if not isinstance( ext, (list,tuple,)): ext = ext.split('|')
  ext = [e[1:] if e[0] == '.' else e for e in ext]
  # remove all first dots
  return re.compile(r'(.*)\.(' + r'|'.join(ext) + r')' + \
                    (r'(\.[0-9]*|)' if ignoreNumbersAfterExtension else '()') + r'$')

def ensureExtension( filename, extL, ignoreNumbersAfterExtension = True ):
  """
  Ensure that filename extension is extL, else adds its extension.

  Extension extL may start with '.' or not. In case it does not, a dot will be
  added.

  A '|' may be specified to treat multiple extensions. In case either one of
  the extensions specified is found, nothing will be changed in the output,
  else the first extension will be added to the file.
  """
  if isinstance(extL, basestring) and '|' in extL: 
    extL = extL.split('|')
  if not isinstance(extL, (list,tuple)):
    extL = [extL]
  extL = ['.' + e if e[0] != '.' else e for e in extL]

  # FIXME: This can be returned earlier by using filter
  if any([checkExtension(filename, ext, ignoreNumbersAfterExtension) for ext in extL]):
    return filename

  # FIXME We should check every extension and see how many composed matches we had before doing this
  ext = extL[0]
  composed = ext.split('.')
  if not composed[0]: composed = composed[1:]
  lComposed = len(composed)
  if lComposed > 1:
    for idx in range(lComposed):
      if filename.endswith( '.'.join(composed[0:idx+1]) ):
        filename += '.' + '.'.join(composed[idx+1:])
        break
    else:
      filename += ext
  else:
    filename += ext
  return filename

def changeExtension( filename, newExtension, knownFileExtensions = ['tgz', 'tar.gz', 'tar.xz','tar',
                                                                    'pic.gz', 'pic.xz', 'pic',
                                                                    'npz', 'npy', 'root'],
                      retryExtensions = ['gz', 'xz'],
                      moreFileExtensions = [],
                      moreRetryExtensions = [],
                      ignoreNumbersAfterExtension = True,
                    ):
  """
  Append string to end of file name but keeping file extension in the end.

  Inputs:
    -> filename: the filename path;
    -> newExtension: the extension to be used by the file;
    -> knownFileExtensions: the known file extensions, use to override all file extensions;
    -> retryExtensions: some extensions are inside other extensions, e.g.
    tar.gz and .gz. This makes regexp operator | to match the smaller
    extension, so the easiest solution is to retry the smaller extensions after
    checking the larger ones.
    -> moreFileExtensions: add more file extensions to consider without overriding all file extensions;
    -> moreRetryExtensions: add more extensions to consider while retrying without overriding the retryExtensions;
    -> ignoreNumbersAfterExtension: whether to ignore numbers after the file extensions or not.

  Output:
    -> the filename with the string appended.
  """
  knownFileExtensions.extend( moreFileExtensions )
  def repStr( newExt ):
    return r'\g<1>' + ( newExt if newExt.startswith('.') else ( '.' + newExt ) )
  str_ = __extRE( knownFileExtensions )
  m = str_.match( filename )
  if m:
    return str_.sub( repStr(newExtension), filename )
  str_ = __extRE( retryExtensions )
  m = str_.match( filename )
  if m:
    return str_.sub( repStr(newExtension), filename )
  else:
    return filename + newExtension

def appendToFileName( filename, appendStr, knownFileExtensions = ['tgz', 'tar.gz', 'tar.xz','tar',
                                                                  'pic.gz', 'pic.xz', 'pic',
                                                                  'npz', 'npy', 'root'],
                      retryExtensions = ['gz', 'xz'],
                      moreFileExtensions = [],
                      moreRetryExtensions = [],
                      ignoreNumbersAfterExtension = True,
                      separator = '_'):
  """
  Append string to end of file name but keeping file extension in the end.

  Inputs:
    -> filename: the filename path;
    -> appendStr: the string to be added to the filename;
    -> knownFileExtensions: the known file extensions, use to override all file extensions;
    -> retryExtensions: some extensions are inside other extensions, e.g.
    tar.gz and .gz. This makes regexp operator | to match the smaller
    extension, so the easiest solution is to retry the smaller extensions after
    checking the larger ones.
    -> moreFileExtensions: add more file extensions to consider without overriding all file extensions;
    -> moreRetryExtensions: add more extensions to consider while retrying without overriding the retryExtensions;
    -> ignoreNumbersAfterExtension: whether to ignore numbers after the file extensions or not.
    -> separator: a string to add as separator

  Output:
    -> the filename with the string appended.
  """
  knownFileExtensions.extend( moreFileExtensions )
  def repStr( lSep ):
    return r'\g<1>' + lSep + appendStr + r'.\g<2>' + r'\g<3>'
  str_ = __extRE(knownFileExtensions)
  m = str_.match(filename)
  if m:
    lSep = ''
    if not(m.group(1).endswith(separator) or appendStr.startswith(separator)):
      lSep = separator
    return str_.sub(repStr(lSep), filename)
  str_ = __extRE(retryExtensions)
  m = str_.match(filename)
  if m:
    lSep = ''
    if not(m.group(1).endswith(separator) or appendStr.startswith(separator)):
      lSep = separator
    return str_.sub(repStr(lSep), filename)
  else:
    return filename + ( separator if not(filename.endswith(separator) or appendStr.startswith(separator)) else '') + appendStr

def getMD5(filepath):
  """
  Get files md5 hash
  """
  import os.path
  import hashlib
  md5_returned = ''
  with open(os.path.expandvars(filepath),'rb') as file_to_check:
    # read contents of the file
    data = file_to_check.read()    
    # pipe contents of the file through
    md5_returned = hashlib.md5(data).hexdigest()
  return md5_returned

def checkFile(filepath, md5sum = None):
  """
  Checks if file exists and if md5sum matches
  """
  import os.path
  filepath = os.path.expandvars(filepath)
  return os.path.isfile(filepath) and \
         (
           md5sum is None or
           getMD5(filepath) == md5sum
         )

from RingerCore.Configure import EnumStringification
class WriteMethod( EnumStringification ):
  """
    Specificate how to write files on cat_files_py
  """
  _ignoreCase = True
  Readlines = 0
  Read = 1
  ShUtil = 2


#@timed
def cat_files_py(flist, ofile, op, logger = None, level = None):
  """
    cat files using python.

    taken from: https://gist.github.com/dimo414/2993381
  """
  op = WriteMethod.retrieve( op )
  if not isinstance(flist, (list, tuple)):
    flist = [flist]
  from RingerCore.Logger import LoggingLevel
  if level is None: level = LoggingLevel.INFO
  with open(ofile, 'wb') as out:
    from RingerCore.util import progressbar
    for fname in progressbar(flist, len(flist), prefix="Merging: ", 
                             disp = True if logger is not None else False, step = 10,
                             logger = logger, level = level ):
      with open(fname,'rb') as f:
        if op is WriteMethod.Readlines:
          out.writelines(f.readlines())
        elif op is WriteMethod.Read:
          out.write(f.read())
        elif op is WriteMethod.ShUtil:
          import shutil
          shutil.copyfileobj(f, out)
      # end of with open(fname)
    # end of for fname in progressbar
  # end of with open(ofile)

def findFile( filename, pathlist, access ):
  """
     Find <filename> with rights <access> through <pathlist>.
     Author: Wim Lavrijsen (WLavrijsen@lbl.gov)
     Copied from 'atlas/Control/AthenaCommon/python/Utils/unixtools.py'
  """

  # special case for those filenames that already contain a path
  if os.path.dirname( filename ):
    if os.access( filename, access ):
      return filename

  # test the file name in all possible paths until first found
  for path in pathlist:
    f = os.path.join( path, filename )
    if os.access( f, access ):
      return f

  # no such accessible file avalailable
  return None  

def mkdir_p(path):
  import errno
  path = os.path.expandvars( path )
  try:
    if not os.path.exists( path ):
      os.makedirs(path)
  except OSError as exc: # Python >2.5
    if exc.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else: raise

def getFiles(folder, ftype = os.path.isfile):
  """
  As in expand folders, but without recursion
  """
  return [ os.path.join(folder,f) for f in sorted(os.listdir(folder)) if ftype( os.path.join(folder,f) ) ]
