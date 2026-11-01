// Category: Uninitialized Variables (Success Case)
// Expected Result: Index should be initialized before using as array index

#include <iostream>

int main() {
    int arr[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    int index = 0;  // SUCCESS: Initialized to a valid index
    
    std::cout << "Value: " << arr[index] << std::endl;
    
    return 0;
}
