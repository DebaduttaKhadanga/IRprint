// How many primes are smaller than limit?
int prime_counter(int limit)
{
    int total = 0;
    for (int candidate = 2; candidate < limit; candidate++)
    {
        int prime_flag = 1;
        for (int div = 2; div * div <= candidate; div++)
            if (candidate % div == 0) { prime_flag = 0; break; }
        if (prime_flag)
            total++;
    }
    return total;
}
