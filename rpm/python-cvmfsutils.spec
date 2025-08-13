# OBS expects the name %%release_prefix; do not change the name
%define release_prefix 1

Summary: Inspect CernVM-FS repositories
Name: python-cvmfsutils
Version: %{version}
Release: %{release_prefix}%{?dist}
Source0: cvmfsutils-%{version}.tar.gz
License: (c) 2015 CERN - BSD License
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Rene Meusel <rene.meusel@cern.ch>
Url: http://cernvm.cern.ch

BuildRequires: python3
BuildRequires: python3-rpm-macros
BuildRequires: python3-pip
BuildRequires: python3-setuptools

Requires: python3-dateutil
Requires: python3-requests
Requires: python3-m2crypto

%description
The CernVM-FS python package allows for the inspection of CernVM-FS
repositories using python. In particular to browse their file catalog
hierarchy, inspect CernVM-FS repository manifests (a.k.a. .cvmfspublished
files) and the history of named snapshots inside any CernVM-FS repository.

%prep
#%%setup -n %{name}-%{version} -n %{name}-%{version}
%autosetup -n cvmfsutils-%{version}

%build
# No build step needed - pip will handle setup.cfg via setup.py

%install
# Install directly from the source tarball - pip handles setup.cfg via setup.py
python3 -m pip install --no-deps --root=%{buildroot} %{_sourcedir}/cvmfsutils-%{version}.tar.gz

%clean
rm -rf $RPM_BUILD_ROOT

%files
%license COPYING
%doc README.md
%{_bindir}/*
%{python3_sitelib}/*

%changelog
* Wed Aug 13 2025 CI Build - %{version}-1
- Modernize build system to use setup.cfg with setuptools
- Update to use setuptools-scm for version management  
- Keep minimal setup.py for compatibility
- Update README reference to README.md

* Fri Apr 26 2024 Dave Dykstra <dwd@fnal.gov>> - 0.5.0-1
- Convert from python2 to python3
- Add cvmfs_search util

* Fri Aug 09 2019 Dave Dykstra <dwd@fnal.gov>> - 0.4.2-1
- Prevent crashing on new "Y" .cvmfspublished key

* Fri Apr 06 2018 Dave Dykstra <dwd@fnal.gov>> - 0.4.1-2
- Add a changelog
- Make builds more seamless on OBS
