#include <stdio.h>
#include <stdlib.h>

int globalCounter = 0;

int sumArray(int* arr, int n) {
    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += arr[i];
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};

    int result = 0;
    for (int i = 0; i < 5; i++) {
        result += data[i] * data[i];  // Assuming the inner loop was redundant and replaced with self-multiplication
    }

    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);

    int divisor = 0;
    if (divisor != 0) {
        printf("Ratio: %d\n", result / divisor);
    } else {
        printf("Division by zero error\n");
    }

    return 0;
}