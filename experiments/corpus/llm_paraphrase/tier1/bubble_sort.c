// Sorts numbers ascending by repeatedly swapping neighbours
void sort_numbers(int *nums, int len)
{
    for (int pass = 0; pass < len - 1; pass++)
        for (int k = 0; k < len - 1 - pass; k++)
            if (nums[k] > nums[k + 1])
            {
                int saved = nums[k];
                nums[k] = nums[k + 1];
                nums[k + 1] = saved;
            }
}
