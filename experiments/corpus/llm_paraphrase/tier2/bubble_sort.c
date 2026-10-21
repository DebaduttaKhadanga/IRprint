void sort_numbers(int *nums, int len)
{
    int pass = 0;
    while (pass < len - 1) {
        int k = 0;
        while (k < len - 1 - pass) {
            if (!(nums[k] <= nums[k + 1])) {
                int saved = nums[k];
                nums[k] = nums[k + 1];
                nums[k + 1] = saved;
            }
            k++;
        }
        pass++;
    }
}
