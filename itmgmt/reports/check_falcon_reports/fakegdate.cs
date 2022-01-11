using System;
using System.Globalization;

class fakegdate
{
    static int Main(String[] args)
    {
        String whenspec = "today";
        String whenformat = "+%d/%b/%Y";
        for (var i = 0; i < args.Length; i++)
        {
            var arg = args[i];
            if (arg == "-d")
            {
                i++;
                whenspec = args[i];
            }
            else if (arg.StartsWith("+"))
            {
                whenformat = arg;
            }
            else
            {
                Console.Error.WriteLine("unexpected argument ({0}): {1}", i, arg);
                return 1;
            }
        }
        DateTime when;
        if (whenspec == "today")
        {
            when = DateTime.Now;
        }
        else if (whenspec == "yesterday")
        {
            when = DateTime.Now - TimeSpan.FromDays(1);
        }
        else
        {
            Console.Error.WriteLine("unsupported date spec: {0}", whenspec);
            return 1;
        }
        if (whenformat == "+%d/%b/%Y")
        {
            whenformat = "dd/MMM/yyyy";
        }
        else
        {
            Console.Error.WriteLine("unsupported date format: {0}", whenformat);
            return 1;
        }
        var whenstr = when.ToString(whenformat, CultureInfo.InvariantCulture);
        Console.WriteLine("{0}", whenstr);
        return 0;
    }
}
