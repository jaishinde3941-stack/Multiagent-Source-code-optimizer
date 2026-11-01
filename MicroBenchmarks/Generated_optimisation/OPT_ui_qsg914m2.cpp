#include <stdio.h>
#include <stdlib.h>

int globalCounter = 0;

int sumArray(int* arr, int n) {
    int sum = 0;
    for (int i = 0; i < n-1; i++) {
        for (int j = i+1; j < n; j++) {
            sum += arr[i] * arr[j];
        }
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};
    int result = 0;
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
            if (i != j) {
                result += data[i] * data[j];
            }
        }
    }
    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);
    int divisor = 1; // Avoid division by zero
    if (divisor != 0) {
        printf("Ratio: %d\n", result / divisor);
    } else {
        printf("Error: Division by zero\n");
    }
    return 0;
}