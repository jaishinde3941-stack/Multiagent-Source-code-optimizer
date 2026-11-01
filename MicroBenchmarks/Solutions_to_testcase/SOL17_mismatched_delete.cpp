// Category: Memory Management Errors (Success Case)
// Expected Result: Use delete[] for array allocations

#include <iostream>

int main() {
    int* arr = new int[10];
    
    for (int i = 0; i < 10; i++) {
        arr[i] = i;
    }
    
    delete[] arr;  // SUCCESS: Used delete[] for array
    
    return 0;
}
