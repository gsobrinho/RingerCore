numpy_tgz_file="$DEP_AREA/numpy.tgz"
numpy_install_path="$INSTALL_AREA/numpy"; numpy_install_path_bslash="$INSTALL_AREA_BSLASH/numpy"

INSTALL_NUMPY=0

test -d "$numpy_install_path/site-packages" && add_to_env PYTHONPATH "$numpy_install_path/site-packages"

source "$ROOTCOREBIN/../RootCoreMacros/retrieve_python_info.sh" --numpy-info \
    || { echo "Couldn't load python information." && exit 1;}


 Check if we need to install numpy:
if test -n "$PYTHON_NUMPY_PATH"; then
  # No need to install it...
  echo "No need to install numpy."
  if test -n "$RINGERCORE_DBG_LEVEL"; then
    echo "Found numpy path as: $PYTHON_NUMPY_PATH"
  fi
  test "$NUMPY_LCG" -eq "1" && add_to_env_file PYTHONPATH "$PYTHON_NUMPY_PATH" \
                            && echo "Using LCG numpy." && return 0;
  test "$PYTHON_NUMPY_PATH" != "$(readlink -f "$numpy_install_path/site-packages")/" \
       && echo "Using system numpy." \
       && return 0;
  # If we get here, then environment must be local, we will only add it the environment file.
else
  # Otherwise we need to install
  INSTALL_NUMPY=1
fi

INSTALL_NUMPY=1

if test "$INSTALL_NUMPY" -eq "1"; then
  numpy_version="1.10.4"

  if test \! -f $numpy_tgz_file; then
    echo "Downloading ${numpy_tgz_file}..."
    numpy_afs_path="/afs/cern.ch/user/w/wsfreund/public/misc/numpy.tgz"
    if test -f $numpy_afs_path; then
      cp "$numpy_afs_path" "$numpy_tgz_file"
    else
      if testtest  "$RCM_GRID_ENV" -eq "1"; then
        echo "Cannot reach numpy source files. Cannot download it from grid." && exit 1;
      fi
      curl -s -o "$numpy_tgz_file" "http://sourceforge.net/projects/numpy/files/NumPy/${numpy_version}/numpy-${numpy_version}.tar.gz/download" \
        || { echo "Couldn't download numpy!" && return 1; }
    fi
  fi

  echo "Installing Numpy..."
  numpy_source_tmp_dir=$(mktemp -d)
  numpy_folder=$(tar xfzv "$numpy_tgz_file" --skip-old-files -C $numpy_source_tmp_dir  2> /dev/null)
  test -z "$numpy_folder" && { echo "Couldn't extract numpy!" && return 1;}
  numpy_folder=$(echo "$numpy_folder" | cut -f1 -d ' ' )
  numpy_folder="$numpy_source_tmp_dir/${numpy_folder%%\/*}";
  if test -e "$numpy_install_path"; then
    rm -r "$numpy_install_path" \
      || { echo "Couldn't remove old installed numpy. Please remove it manually on path \"$numpy_install_path\" and try again." && return 1; }
  fi
  mkdir -p "$numpy_install_path"
  cd "$numpy_folder"; tmp_numpy_install_folder="$numpy_install_path/lib/$PYTHON_LIB_VERSION/site-packages/"
  mkdir -p "$tmp_numpy_install_folder"
  export PYTHONPATH="$tmp_numpy_install_folder:$PYTHONPATH"
  python setup.py install --prefix "$numpy_install_path" > /dev/null || { echo "Couldn't install numpy." && return 1;}
  cd - > /dev/null
  mv $(find $numpy_install_path -name "site-packages" -type d) "$numpy_install_path"
  rm -r $(find $numpy_install_path  -maxdepth 1 -mindepth 1 -not -name "site-packages" -a -not -name "bin")
  rm -r $numpy_source_tmp_dir
fi

test -d "$numpy_install_path"                            && export numpy_install_path_bslash
test -d "$numpy_install_path/bin"                        && add_to_env_file PATH "$numpy_install_path_bslash/bin"
test -d "$numpy_install_path/site-packages"              && add_to_env_file PYTHONPATH "$numpy_install_path_bslash/site-packages"
test -d "$numpy_install_path/site-packages/core/include" && add_to_env_file CPATH "$numpy_install_path_bslash/site-packages"

source "$NEW_ENV_FILE"
