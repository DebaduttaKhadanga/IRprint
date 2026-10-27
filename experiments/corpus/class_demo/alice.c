/* Assignment 3: sorting and statistics (original work). */
void sort_scores(int *scores, int n) {
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - 1 - i; j++) {
            if (scores[j] > scores[j + 1]) {
                int tmp = scores[j];
                scores[j] = scores[j + 1];
                scores[j + 1] = tmp;
            }
        }
    }
}

int highest_score(int *scores, int n) {
    int best = scores[0];
    for (int i = 1; i < n; i++) {
        if (scores[i] > best) {
            best = scores[i];
        }
    }
    return best;
}

double average_score(int *scores, int n) {
    long total = 0;
    for (int i = 0; i < n; i++) {
        total += scores[i];
    }
    return n > 0 ? (double)total / n : 0.0;
}
