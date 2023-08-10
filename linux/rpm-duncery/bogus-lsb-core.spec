Name:           bogus-lsb-core
Version:        4.1
Release:        2%{?dist}
Summary:        Bogus Linux Standard Base
License:        LicenseRef-Fedora-Public-Domain

%ifarch %{ix86}
Requires:       /%{_lib}/ld-linux.so.2
%else
Requires:       /%{_lib}/ld-linux-%{__isa}.so.2
%endif

%if %{__isa_bits} == 64
Provides:       ld-lsb.so.3()(64bit)
%else
Provides:       ld-lsb.so.3
%endif

BuildRequires:  ( /bin/ln or %{_bindir}/ln )

# Skip ldconfig as part of __os_install_post
# since it keeps deleting the symlink
%define __brp_ldconfig %{nil}


%description
Terrible tricks to run LSB-dependent binaries on the
growing number of distributions that are giving up on LSB.


%prep

%build

%install
mkdir %{buildroot}/%{_lib}
cd %{buildroot}/%{_lib}
%ifarch %{ix86}
#touch ld-linux.so.2
ln -sv ld-linux.so.2 ld-lsb.so.3
%else
#touch ld-linux-%{__isa}.so.2
ln -sv ld-linux-%{__isa}.so.2 ld-lsb-%{__isa}.so.3
%endif
ls -alF

%files
%ifarch %{ix86}
/%{_lib}/ld-lsb.so.3
%else
/%{_lib}/ld-lsb-%{__isa}.so.3
%endif

%changelog
