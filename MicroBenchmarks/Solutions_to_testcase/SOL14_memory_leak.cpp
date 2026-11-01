// Category: Memory Management Errors (Success Case)
// Expected Result: Allocated memory should be deleted

#include <iostream>

int main() {
    int* ptr = new int[100];
    
    for (int i = 0; i < 100; i++) {
        ptr[i] = i;
    }
    
    std::cout << "Sum of first element: " << ptr[0] << std::endl;
    
    delete[] ptr;  // SUCCESS: Memory freed correctly
    
    return 0;
}
