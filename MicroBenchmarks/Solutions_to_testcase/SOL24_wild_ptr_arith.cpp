// Category: Pointer Errors (Success Case)
// Expected Result: Keep pointer arithmetic within valid array bounds

#include <iostream>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int* ptr = arr;
    
    ptr += 4;  // SUCCESS: Within valid array bounds
    std::cout << "Value: " << *ptr << std::endl;
    
    return 0;
}
