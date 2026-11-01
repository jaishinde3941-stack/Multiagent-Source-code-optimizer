#include <iostream>

int main() {
    int x = 0;  // Initialize x to avoid undefined behavior
    int y = 10;
    int result = x + y;
    std::cout << "Result: " << result << std::endl;
    return 0;
}