#include <stdio.h>

int main(int argc, char **argv)
{
    for (int i = 1; i < argc; i++)
    {
        printf("%d:\t%s\n", i, argv[i]);
    }
    return 0;
}
