#include <stdio.h>

int globalCounter = 0;  // initialized global variable

int sumArray(int* arr, int n) {
    int sum = 0;  // initialized local variable
    for (int i = 0; i < n; i++) {  // corrected loop condition
        sum += arr[i];
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};
    int result = 0;
    int sumOfSquares = 0;
    for (int i = 0; i < 5; i++) {
        sumOfSquares += data[i] * data[i];
    }
    result = sumOfSquares * sumOfSquares;

    printf("Sum:     %d\n", sumArray(data, 5));
    printf("Result:  %d\n", result);
    printf("Counter: %d\n", globalCounter);  // initialized global

    int divisor = 1;  // avoid division by zero
    if (divisor != 0) {
        printf("Ratio: %d\n", result / divisor);
    } else {
        printf("Division by zero error\n");
    }

    return 0;
}