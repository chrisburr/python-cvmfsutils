# OBS expects the name %%release_prefix; do not change the name
%define release_prefix 1

Summary: Inspect CernVM-FS repositories
Name: python-cvmfsutils
Version: 0.6.0
Release: %{release_prefix}%{?dist}
Source0: cvmfsutils-0.6.0.tar.gz
License: (c) 2015 CERN - BSD License
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-0.6.0-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Rene Meusel <rene.meusel@cern.ch>
Url: http://cernvm.cern.ch

%if 0%{?rhel} == 8
# AlmaLinux/RHEL 8 ships Python 3.6 which is too old; use python3.11 from AppStream.
# python3.11-dateutil is not packaged for EL8, so it is bundled via pip below.
%global __python3 /usr/bin/python3.11
%global python3_sitelib /usr/lib/python3.11/site-packages

BuildRequires: python3.11
BuildRequires: python3.11-rpm-macros
BuildRequires: python3.11-pip
BuildRequires: python3.11-setuptools

Requires: python3.11
Requires: python3.11-requests
Requires: python3.11-cryptography
Requires: python3.11-six
%else
BuildRequires: python3
BuildRequires: python3-rpm-macros
BuildRequires: python3-pip
BuildRequires: python3-setuptools

Requires: python3-dateutil
Requires: python3-requests
Requires: python3-cryptography
%endif

%description
The CernVM-FS python package allows for the inspection of CernVM-FS
repositories using python. In particular to browse their file catalog
hierarchy, inspect CernVM-FS repository manifests (a.k.a. .cvmfspublished
files) and the history of named snapshots inside any CernVM-FS repository.

%prep
#%%setup -n %{name}-0.6.0 -n %{name}-0.6.0
%autosetup -n cvmfsutils-0.6.0

%build
# No build step needed - pip install handles everything

%install
%{__python3} -m pip install --no-deps --root=%{buildroot} %{_sourcedir}/cvmfsutils-0.6.0.tar.gz
%if 0%{?rhel} == 8
# python3.11-dateutil is not packaged for EL8; bundle it (six comes from system)
%{__python3} -m pip install --no-deps --root=%{buildroot} 'python-dateutil >= 1.4.1'
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%license COPYING
%doc README.md
%{_bindir}/*
%{python3_sitelib}/*

%changelog
# - Replace M2Crypto dependency with cryptography library

* Wed Aug 13 2025 Chris Burr <christopher.burr@cern.ch> - 0.6.0-1
- Modernize build system to use pyproject.toml with setuptools
- Use setuptools-scm for version management
- Add SUSE/OBS compatibility

* Fri Apr 26 2024 Dave Dykstra <dwd@fnal.gov>> - 0.5.0-1
- Convert from python2 to python3
- Add cvmfs_search util

* Fri Aug 09 2019 Dave Dykstra <dwd@fnal.gov>> - 0.4.2-1
- Prevent crashing on new "Y" .cvmfspublished key

* Fri Apr 06 2018 Dave Dykstra <dwd@fnal.gov>> - 0.4.1-2
- Add a changelog
- Make builds more seamless on OBS
