#!/usr/bin/env perl
# vim: shiftwidth=4 tabstop=4 expandtab ft=perl
use warnings;
use strict;
use Data::Dumper;
use Date::Parse;


my $GOODCOUNT = 0;
my $BADCOUNT = 0;
my @REGEXFIELDS = (
    '(?<h>[(\w\d\.:)]+)',
    '(?<l>\S+)',
    '(?<u>\S.*)',
    '\[(?<t>.+?)\]',
    '"(?<r>.*?)"',
    '(?<s>\d+)',
    '(?<b>-|\d+)',
    '"(?<referer>.*?)"',
    '"(?<useragent>.*?)"',
);
my $STARTREGEX = '^' . join(' ', @REGEXFIELDS[0..2]);
my $ENDREGEX = ' ' . join(' ', @REGEXFIELDS[3..8]) . '$';
my $header = undef;

while (<>) {
    chomp;
    my $result = 'unknown';
    my $dumplineandexit = 0;
    my %startdata = ();
    my %enddata = ();
    if (m/$ENDREGEX/) {
        %enddata = %+;
        my $startstring = $`;
        if ($startstring =~ m/$STARTREGEX/) {
            $result = 'good';
            %startdata = %+;
            #if ($startdata{'u'} =~ / / or $startdata{'u'} eq "'") {
            #    $result = 'dangeruser';
            #}
        } else {
            $result = 'badstart';
        }
    } else {
        $result = 'badend';
    }
    if ($result eq 'good') {
        $GOODCOUNT++;
        my ($ss,$mm,$hh,$day,$month,$year,$zone) = strptime($enddata{t});
        $year += 1900;
        $month += 1;
        my $bytes = $enddata{b} eq '-' ? 0 : int($enddata{b});
        my ($method, $path, $httpver) = split(' ', $enddata{r}, 3);
        my @names = ();
        my @specs = ();
        my @values = ();
        push @names, 'time';
        push @specs, '%04d-%02d-%02d %02d:%02d:%02d';
        push @values, $year, $month, $day, $hh, $mm, $ss;
        push @names, 'user'; push @specs, '%s'; push @values, $startdata{u};
        push @names, 'code'; push @specs, '%s'; push @values, $enddata{s};
        push @names, 'size'; push @specs, '%d'; push @values, $bytes;
        push @names, 'meth'; push @specs, '%s'; push @values, $method // '';
        push @names, 'path'; push @specs, '%s'; push @values, $path // '';
        if (!defined($header)) {
            $header = join("\t", @names);
            print $header, "\n";
        }
        printf(join("\t", @specs) . "\n", @values);
    } else {
        $BADCOUNT++;
    }
    if ($result eq 'dangeruser') {
        my $dangeruser = $startdata{u};
        my $currentfile = $ARGV;
        my $lineinfile = ${\*ARGV}->input_line_number;
        print STDERR "DANGERUSER:  $dangeruser\n";
        print STDERR "      file:  $currentfile\n";
        print STDERR "      line:  $lineinfile\n";
        print STDERR "      data:  $_\n";
        print STDERR "\n";
    }
    if ($dumplineandexit) {
        print STDERR ".:  $.\n";
        print STDERR "_:  $_\n";
        print STDERR "r:  $result\n";
        INSPECTREGEX: for (my $right = 0; $right < @REGEXFIELDS; $right++) {
            my $partialregex = '^' . join(' ', @REGEXFIELDS[0..$right]);
            my $previousremainder = $' // '<<>>';
            if (m/$partialregex/) {
                print STDERR "$right:  $+\n";
            } else {
                print STDERR "x:  $previousremainder\n";
                print STDERR Dumper(\%+);
                last INSPECTREGEX;
            }
        }
        print STDERR 's: ', Dumper(\%startdata);
        print STDERR 'e: ', Dumper(\%enddata);
        exit 1;
    }
}

print STDERR "good: $GOODCOUNT\n";
print STDERR "bad:  $BADCOUNT\n";
