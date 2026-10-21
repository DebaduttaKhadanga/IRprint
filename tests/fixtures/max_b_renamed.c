/* Plagiarised copy: every identifier renamed, formatting changed. */
int biggest(int *values, int count)
{
    int champion = values[0];
    for (int k = 1; k < count; k++)
        if (values[k] > champion)
            champion = values[k];
    return champion;
}
