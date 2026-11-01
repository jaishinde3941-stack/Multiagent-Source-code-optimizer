// Category: Memory Management Errors
// Error: Mismatched new/delete (array vs single)

#include <iostream>

int main() {
    int* arr = new int[10];
    
    for (int i = 0; i < 10; i++) {
        arr[i] = i;
    }
    
    delete arr;  // ERROR: Should be delete[] for array allocation
    
    return 0;
}
