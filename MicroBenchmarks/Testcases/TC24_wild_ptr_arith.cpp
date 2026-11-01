// Category: Pointer Errors
// Error: Wild pointer arithmetic

#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int* ptr = arr;
    
    ptr += 100;  // ERROR: Pointer now points way beyond valid memory
    std::cout << "Value: " << *ptr << std::endl;
    
    return 0;
}
