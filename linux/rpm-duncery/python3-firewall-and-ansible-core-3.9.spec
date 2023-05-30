Name:           python3-firewall-and-ansible-core
Version:        3.9
Release:        1%{?dist}
Summary:        Ensure ansible-core can find python3-firewall
License:        LicenseRef-Fedora-Public-Domain

BuildArch:      noarch
Requires:       python3.9-firewall
Requires:       python3.9dist(ansible-core)

%description
Ensure ansible-core can find python3-firewall
by using the same "/usr/lib/python3.x/...".


%prep
%build
%install
%files
%changelog
