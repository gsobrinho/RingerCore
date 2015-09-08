#
# Installs boost_1_58_0. It will take a while, only source this if you are sure
# that your system does not contains the boost needed version already installed.
#

test "x$1" = "x" -o "x$2" = "x" -o "x$3" = "x" && echo "$0: Wrong number of arguments" && exit 1

MAKEFILE=$1
NEW_ENV_FILE=$2
PYTHON_INCLUDE=$3

CXX=`root-config --cxx`

BOOST_LOCAL_PATH=\${ROOTCOREBIN}/../RingerCore/cmt
# This are the not expanded versions of boost include/library paths:
boost_include_ne=$BOOST_LOCAL_PATH/include
boost_lib_ne=$BOOST_LOCAL_PATH/lib
# And the normal versions of the paths
boost_include=$(eval echo "$BOOST_LOCAL_PATH/include")
boost_lib=$(eval echo "$BOOST_LOCAL_PATH/lib")

boost_file="/afs/cern.ch/user/w/wsfreund/public/boost_1_58_0.tar.gz"

# Do not recheck whether build was successful:
DO_NOT_CHECK=0

if test \! -f `eval echo "$boost_include/boost/python.hpp"` -o \! -d `eval echo "$boost_lib/"`
then
  if test \! -f boost_test.h.gch
  then
    if ! $CXX $PYTHON_INCLUDE -P boost_test.h -o boost_test.h.gch > /dev/null 2> /dev/null
    then
      echo "It is needed to install boost python library." 
      if test \! -f boost_1_58_0.tar.gz 
      then
        if test -f $boost_file
        then
          if ! rsync -rvhzP -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=quiet" $boost_file .
          then
            scp -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" -o "LogLevel=quiet" $boost_file . \
              || { echo "Couldn't download boost from afs!" && exit 1; }
          fi
        else
          if ! wget http://sourceforge.net/projects/boost/files/boost/1.58.0/boost_1_58_0.tar.gz
          then
            echo "Couldn't download boost and there is no afs access to download it." && exit 1 
          fi
        fi
      fi
      test \! -e boost_1_58_0 && { { echo -n "Extracting files..." && tar xfz boost_1_58_0.tar.gz && echo " done!"; } || \
        { echo "Couldn't extract files!" && exit 1; } }
      echo "Installing boost..."
      cd boost_1_58_0
      if ./bootstrap.sh --prefix=`eval echo "$BOOST_LOCAL_PATH"` --with-libraries=python > /dev/null
      then
        echo "Finished setting bootstrap successfully."
      else
        echo "Couldn't source bootstrap.sh." && exit 1
      fi
      if ./b2 install --prefix=`eval echo "$BOOST_LOCAL_PATH"` --with-python -j$ROOTCORE_NCPUS > /dev/null
      then
        echo "Sucessfully compiled boost."
      else
        echo "Couldn't install boost." && exit 1
      fi
      cd - > /dev/null
      sleep 3
    else
      echo "Boost installed at file system"
      DO_NOT_CHECK=1
    fi
  else
    echo "Boost installed at file system"
    DO_NOT_CHECK=1
  fi
else
  echo "Boost needed libraries already installed."
  DO_NOT_CHECK=1
fi

old_field=`$ROOTCOREDIR/scripts/get_field.sh $MAKEFILE PACKAGE_LDFLAGS`
if test "${old_field#*-L$boost_lib}" = "$old_field"
then
  $ROOTCOREDIR/scripts/set_field.sh $MAKEFILE PACKAGE_LDFLAGS "-L$boost_lib $old_field " 
else
  echo "Do not need to add boost_lib"
fi

arch=`root-config --arch`
include_marker="-I"

old_field=`$ROOTCOREDIR/scripts/get_field.sh $MAKEFILE PACKAGE_OBJFLAGS`
if test "${old_field#*$include_marker$boost_include_ne}" = "$old_field"
then
  $ROOTCOREDIR/scripts/set_field.sh $MAKEFILE PACKAGE_OBJFLAGS "-L$boost_lib $old_field $include_marker$boost_include_ne"  
fi

echo "test \"\$(echo \":\$CPATH:\" | grep -q \":$boost_include_ne:\"; echo \$?)\" -ne \"0\" && export CPATH=$boost_include_ne:\$CPATH || true" >> $NEW_ENV_FILE
echo "test \"\$(echo \":\$LD_LIBRARY_PATH:\" | grep -q \":$boost_lib_ne:\"; echo \$?)\" -ne \"0\" && export LD_LIBRARY_PATH=$boost_lib_ne:\$LD_LIBRARY_PATH || true" >> $NEW_ENV_FILE
if test "$arch" = "macosx64"
then
  echo "test \"\$(echo \":\$DYLD_LIBRARY_PATH:\" | grep -q \":$boost_lib_ne:\"; echo \$?)\" -ne \"0\" && export DYLD_LIBRARY_PATH=$boost_lib_ne:\$DYLD_LIBRARY_PATH || true" >> $NEW_ENV_FILE
fi
source $NEW_ENV_FILE || { echo "Couldn't set environment" && exit 1; }

# Final test:
if test "$DO_NOT_CHECK" -ne 1; then
  echo -n "Checking boost installation..." && { `$CXX $PYTHON_INCLUDE -o boost_test.h.gch -P boost_test.h  > /dev/null 2> /dev/null` || { echo "\nBoost couldn't be found!" && exit 1; } && echo " sucessfully installed!"; }
fi
