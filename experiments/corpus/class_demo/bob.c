/* Assignment 3 -- Bob (copied from Alice, identifiers renamed) */
void arrange(int *marks, int count)
{
    for (int a = 0; a < count - 1; a++)
        for (int b = 0; b < count - 1 - a; b++)
            if (marks[b] > marks[b + 1])
            {
                int t = marks[b];
                marks[b] = marks[b + 1];
                marks[b + 1] = t;
            }
}

int top_mark(int *marks, int count)
{
    int top = marks[0];
    for (int a = 1; a < count; a++)
        if (marks[a] > top)
            top = marks[a];
    return top;
}

double mean_mark(int *marks, int count)
{
    long sum = 0;
    for (int a = 0; a < count; a++)
        sum += marks[a];
    return count > 0 ? (double)sum / count : 0.0;
}
